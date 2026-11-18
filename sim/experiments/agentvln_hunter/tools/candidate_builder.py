#!/usr/bin/env python3
"""Map/costmap candidate generation and moving-camera projection for AgentVLN.

The module is deliberately free of instruction semantics: it proposes reachable
ground poses, filters them with the live Nav2 costmap and a trial ComputePathToPose
plan, then projects them into the RGB frame at the image timestamp.
"""
import math
from dataclasses import dataclass, field

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from nav2_msgs.action import ComputePathToPose
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from tf2_geometry_msgs import do_transform_point
from tf2_ros import Buffer, TransformListener

FOOTPRINT = [(-0.184, -0.393), (0.834, -0.393), (0.834, 0.393), (-0.184, 0.393)]


def yaw_of_quat(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def quat_from_yaw(yaw):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def stamp_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


@dataclass
class CostmapView:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    data: np.ndarray

    def cost_at(self, x, y):
        c = int(math.floor((x - self.origin_x) / self.resolution))
        r = int(math.floor((y - self.origin_y) / self.resolution))
        if c < 0 or r < 0 or c >= self.width or r >= self.height:
            return 100
        return int(self.data[r * self.width + c])


def footprint_cells(x, y, yaw, resolution=0.05):
    """Return costmap coordinates of a rotated footprint, including interior samples."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    xs = np.arange(-0.184, 0.834 + 1e-9, 0.07)
    ys = np.arange(-0.393, 0.393 + 1e-9, 0.07)
    pts = []
    for px in xs:
        for py in ys:
            pts.append((x + cy * px - sy * py, y + sy * px + cy * py))
    return pts


def footprint_clear(costmap, x, y, yaw):
    return all(costmap.cost_at(px, py) == 0 for px, py in footprint_cells(x, y, yaw))


def path_cost_clear(costmap, path_poses):
    """Check the planned path itself against the live costmap (0 = free)."""
    if len(path_poses) < 2:
        return False
    for a, b in zip(path_poses[:-1], path_poses[1:]):
        ax, ay = a.pose.position.x, a.pose.position.y
        bx, by = b.pose.position.x, b.pose.position.y
        dist = math.hypot(bx - ax, by - ay)
        n = max(1, int(dist / 0.10))
        for i in range(n + 1):
            t = i / n
            if costmap.cost_at(ax + t * (bx - ax), ay + t * (by - ay)) != 0:
                return False
    return True


def path_length(path_poses):
    return sum(math.hypot(b.pose.position.x - a.pose.position.x,
                          b.pose.position.y - a.pose.position.y)
               for a, b in zip(path_poses[:-1], path_poses[1:]))


@dataclass
class Candidate:
    cid: int = 0
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    distance_from_robot: float = 0.0
    bearing_from_robot: float = 0.0
    path_length: float = 0.0
    plan_status: int = 0
    footprint_ok: bool = False
    path_clear: bool = False
    u: float = 0.0
    v: float = 0.0
    ground_u: float = 0.0
    ground_v: float = 0.0
    ground_in_frame: bool = False
    vis_height_m: float = 0.0
    optical_z: float = 0.0
    expected_range: float = 0.0
    depth_median: float = 0.0
    visible: bool = False
    occluded: bool = False
    reason: str = ''
    extra: dict = field(default_factory=dict)


class CandidateBuilder(Node):
    def __init__(self, name='candidate_builder'):
        super().__init__(name)
        self.costmap = None
        self.last_stats = {}
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.plan_client = ActionClient(self, ComputePathToPose, 'compute_path_to_pose')
        cm_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                            reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(
            __import__('nav_msgs.msg', fromlist=['OccupancyGrid']).OccupancyGrid,
            '/global_costmap/costmap', self.on_costmap, cm_qos)

    def on_costmap(self, msg):
        self.costmap = CostmapView(msg.info.width, msg.info.height, msg.info.resolution,
                                   msg.info.origin.position.x, msg.info.origin.position.y,
                                   np.asarray(msg.data, dtype=np.int8))

    def wait_costmap(self, timeout=10.0):
        end = self.get_clock().now().nanoseconds / 1e9 + timeout
        while self.costmap is None and self.get_clock().now().nanoseconds / 1e9 < end:
            rclpy.spin_once(self, timeout_sec=0.05)
        return self.costmap

    def robot_pose(self, stamp):
        t = self.tf_buffer.lookup_transform('map', 'base_link', stamp, timeout=Duration(seconds=1.0))
        p = t.transform.translation
        return (p.x, p.y, yaw_of_quat(t.transform.rotation))

    def plan(self, start, goal, timeout=2.5):
        if not self.plan_client.wait_for_server(timeout_sec=3.0):
            return 0, []
        g = ComputePathToPose.Goal()
        g.goal.header.frame_id = 'map'
        g.goal.header.stamp = self.get_clock().now().to_msg()
        g.goal.pose.position.x = goal[0]
        g.goal.pose.position.y = goal[1]
        q = quat_from_yaw(goal[2])
        g.goal.pose.orientation.x, g.goal.pose.orientation.y = q[0], q[1]
        g.goal.pose.orientation.z, g.goal.pose.orientation.w = q[2], q[3]
        g.start.header.frame_id = 'map'
        g.start.header.stamp = g.goal.header.stamp
        g.start.pose.position.x = start[0]
        g.start.pose.position.y = start[1]
        qs = quat_from_yaw(start[2])
        g.start.pose.orientation.x, g.start.pose.orientation.y = qs[0], qs[1]
        g.start.pose.orientation.z, g.start.pose.orientation.w = qs[2], qs[3]
        g.planner_id = 'GridBased'
        g.use_start = True
        fut = self.plan_client.send_goal_async(g)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=3.0)
        handle = fut.result()
        if handle is None or not handle.accepted:
            return 0, []
        rf = handle.get_result_async()
        end = self.get_clock().now().nanoseconds / 1e9 + timeout
        while not rf.done() and self.get_clock().now().nanoseconds / 1e9 < end:
            rclpy.spin_once(self, timeout_sec=0.02)
        if not rf.done():
            handle.cancel_goal_async()
            return 0, []
        result = rf.result()
        if result is None or result.result is None:
            return 0, []
        return int(result.status), list(result.result.path.poses)

    def build(self, image_stamp, camera_info, robot_pose, distances=(1.4, 1.7, 2.0),
              angles_deg=(-26, -13, 0, 13, 26), max_candidates=18):
        if self.costmap is None and not self.wait_costmap():
            return []
        rx, ry, ryaw = robot_pose
        out = []
        stats = {'sampled': 0, 'footprint_rejected': 0, 'plan_rejected': 0, 'path_rejected': 0}
        for d in distances:
            for adeg in angles_deg:
                ang = ryaw + math.radians(adeg)
                x = rx + d * math.cos(ang)
                y = ry + d * math.sin(ang)
                stats['sampled'] += 1
                c = Candidate(x=x, y=y, yaw=ang, distance_from_robot=d,
                              bearing_from_robot=math.radians(adeg))
                c.footprint_ok = footprint_clear(self.costmap, x, y, ang)
                if not c.footprint_ok:
                    c.reason = 'footprint_not_clear'
                    stats['footprint_rejected'] += 1
                    out.append(c)
                    continue
                status, path = self.plan((rx, ry, ryaw), (x, y, ang))
                c.plan_status = status
                if status != 4 or len(path) < 2:
                    c.reason = 'trial_plan_failed'
                    stats['plan_rejected'] += 1
                    out.append(c)
                    continue
                c.path_length = path_length(path)
                c.path_clear = path_cost_clear(self.costmap, path)
                if not c.path_clear:
                    c.reason = 'trial_path_crosses_obstacle'
                    stats['path_rejected'] += 1
                    out.append(c)
                    continue
                out.append(c)
        out = [c for c in out if c.reason == '']
        stats['valid'] = len(out)
        self.last_stats = stats
        out.sort(key=lambda c: (c.distance_from_robot, c.bearing_from_robot))
        out = out[:max_candidates]
        return out

    def project(self, candidates, image_stamp, camera_info, depth, image_shape, vis_height=0.5):
        fx, fy = camera_info.k[0], camera_info.k[4]
        cx, cy = camera_info.k[2], camera_info.k[5]
        h, w = image_shape
        try:
            tf = self.tf_buffer.lookup_transform(
                camera_info.header.frame_id or 'agentvln_camera_optical_frame', 'map',
                image_stamp, timeout=Duration(seconds=1.0))
        except Exception as exc:
            for c in candidates:
                c.reason = 'tf_unavailable: %s' % exc
            return candidates

        def project_at(c, z):
            p = PointStamped()
            p.header.frame_id = 'map'
            p.header.stamp = image_stamp
            p.point.x, p.point.y, p.point.z = c.x, c.y, z
            q = do_transform_point(p, tf)
            if q.point.z <= 0.2:
                return None
            return (q, fx * q.point.x / q.point.z + cx, fy * q.point.y / q.point.z + cy)

        for c in candidates:
            c.vis_height_m = vis_height
            g = project_at(c, 0.0)
            if g is not None:
                c.ground_u, c.ground_v = g[1], g[2]
                c.ground_in_frame = bool(0 <= g[1] < w and 0 <= g[2] < h)
            d = project_at(c, vis_height)
            if d is None:
                c.reason = 'behind_camera'
                continue
            q, u, v = d
            c.u, c.v, c.optical_z = u, v, q.point.z
            if not (0 <= u < w and 0 <= v < h):
                c.reason = 'outside_image_beacon'
                continue
            c.expected_range = math.sqrt(q.point.x ** 2 + q.point.y ** 2 + q.point.z ** 2)
            ui, vi = int(round(u)), int(round(v))
            win = depth[max(0, vi - 3):min(h, vi + 4), max(0, ui - 3):min(w, ui + 4)]
            valid = win[np.isfinite(win) & (win > 0.05)]
            if valid.size == 0:
                c.reason = 'no_depth_at_projection'
                continue
            c.depth_median = float(np.median(valid))
            c.occluded = bool(c.depth_median < c.expected_range - 0.35)
            if c.occluded:
                c.reason = 'depth_occluded'
                continue
            c.visible = True
        return candidates
