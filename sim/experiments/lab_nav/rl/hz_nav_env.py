"""A reinforcement-learning environment on the lab navigation scene.

The environment drives the same lean stack the navigation baseline uses: the
same world, the same scan, the same Ackermann model and the same ``/cmd_vel``
entry point.  That is deliberate -- a policy that only beats a different
simulator has not been compared to anything.

Interface
---------
``reset(goal=None)``  teleports to the spawn, zeroes the command, waits for the
                      vehicle to settle, reads the pose back and returns an
                      observation.  The readback is checked, not assumed.
``step(action)``      holds one command for one control period of simulated
                      time and returns ``(obs, reward, terminated, truncated,
                      info)``.

Observation (float32, 76 values, all in [-1, 1])
    0..71   the scan downsampled 10:1 by taking the minimum of each group, so a
            thin obstacle survives the reduction; divided by 3 m and clipped
    72      distance to the goal in the odometry frame / 6 m
    73      bearing to the goal, wrapped to [-pi, pi], divided by pi
    74      last commanded linear velocity / 0.26
    75      last commanded yaw rate / 0.20

Action (float32, 2 values, in [-1, 1])
    linear velocity  -> [0, 0.26] m/s   (forward only, matching the baseline's
                                         allow_reversing: false)
    yaw rate         -> [-0.20, 0.20] rad/s

What the policy can see and what it cannot
------------------------------------------
The policy sees the scan and the wheel odometry only.  The goal is fixed in the
map frame and is expressed through the odometry frame using the map-to-odometry
offset measured *once at reset*; drift after that is the policy's problem, as it
would be on a robot that localised once and then dead-reckoned.

Ground truth is used for three things and no others: teleporting, scoring
success, and detecting collisions.  Those uses are recorded in ``info`` so no
result can quietly present a truth-fed policy as a sensor-only one.
"""
import math
import subprocess
import threading
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from ros_gz_interfaces.msg import Contacts
from sensor_msgs.msg import LaserScan

SCAN_BEAMS = 720
SCAN_GROUPS = 72
SCAN_MAX_M = 3.0
MAX_V = 0.26
MAX_W = 0.20
CONTROL_DT = 0.10          # simulated seconds per step
EPISODE_SIM_S = 60.0
GOAL_TOL = 0.25
SPAWN = (-0.21, -0.77, 0.165, 0.0)
WORLD = 'hz_lab_2d'
MODEL = 'hz_hunter_full'


def _wrap(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class _Bridge(Node):
    """Collects the few topics the environment needs."""

    def __init__(self):
        super().__init__('hz_nav_env')
        self.scan = None
        self.scan_stamp = None
        self.odom = None
        self.truth = None
        self.contacts = []
        self.raw_contacts = 0
        self.sim_time = None
        self.cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(LaserScan, '/scan', self._on_scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, '/odom', self._on_odom, qos_profile_sensor_data)
        self.create_subscription(Odometry, '/ground_truth', self._on_truth,
                                 qos_profile_sensor_data)
        self.create_subscription(Contacts, '/contacts', self._on_contacts,
                                 qos_profile_sensor_data)
        self.create_subscription(Clock, '/clock', self._on_clock, qos_profile_sensor_data)

    def _on_scan(self, msg):
        self.scan = np.asarray(msg.ranges, dtype=np.float32)
        self.scan_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

    def _on_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.odom = (p.x, p.y, _yaw(q),
                     msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def _on_truth(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.truth = (p.x, p.y, _yaw(q))

    def _on_contacts(self, msg):
        for c in msg.contacts:
            names = sorted([c.collision1.name, c.collision2.name])
            self.contacts.append(tuple(names))
            self.raw_contacts += 1

    def _on_clock(self, msg):
        self.sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9

    def wait_sim(self, seconds, timeout_wall=60.0):
        """Advance by simulated seconds, not wall seconds."""
        start_sim = self.sim_time
        start_wall = time.time()
        while True:
            if self.sim_time is not None and self.sim_time - start_sim >= seconds:
                return True
            if time.time() - start_wall > timeout_wall:
                return False
            time.sleep(0.002)


def _vehicle_contacts(pairs):
    """Contacts with the floor under a wheel are normal rolling, not a crash."""
    out = []
    for a, b in pairs:
        both = f'{a} {b}'
        wheel = ('wheel' in both) or ('tire' in both)
        floor = 'floor' in both or 'ground' in both
        if wheel and floor:
            continue
        out.append((a, b))
    return out


def teleport(x, y, z, yaw):
    """Move the model with a Gazebo service call; returns True on an accepted request."""
    req = (f'name: "{MODEL}", position: {{x: {x}, y: {y}, z: {z}}}, '
           f'orientation: {{z: {math.sin(yaw / 2.0)}, w: {math.cos(yaw / 2.0)}}}')
    cmd = ['ign', 'service', '-s', f'/world/{WORLD}/set_pose',
           '--reqtype', 'ignition.msgs.Pose', '--reptype', 'ignition.msgs.Boolean',
           '--timeout', '3000', '--req', req]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return 'data: true' in out.stdout
    except (subprocess.SubprocessError, OSError):
        return False


class HzLabNavEnv(object):
    """Gymnasium-shaped, but without the dependency (the machine has no pip)."""

    def __init__(self, seed=0, goal=None, episode_s=EPISODE_SIM_S,
                 reward_variant='progress'):
        self.rng = np.random.default_rng(seed)
        self.fixed_goal = goal
        self.episode_s = episode_s
        # 'progress' pays only for getting closer; because contact costs more
        # than idling, a policy can learn to stop a metre short.  The
        # 'progress_distance' variant also charges for remaining distance, so
        # standing still is not free.
        self.reward_variant = reward_variant
        self._node = None
        self._thread = None
        self._running = False
        self._episode = 0
        self._goal_map = None
        self._odom0 = None
        self._truth0 = None
        self._last_action = (0.0, 0.0)
        self._prev_dist = None
        self._prev_truth = None
        self._stuck = 0
        self._sim_start = None
        self._steps = 0
        self.last_reset_report = None

    # -- lifecycle -------------------------------------------------------
    def start(self):
        if self._node is not None:
            return self
        rclpy.init()
        self._node = _Bridge()
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        deadline = time.time() + 20.0
        while self._node.sim_time is None and time.time() < deadline:
            time.sleep(0.05)
        if self._node.sim_time is None:
            raise RuntimeError('no /clock: is the lean stack running?')
        return self

    def _spin(self):
        while self._running and rclpy.ok():
            try:
                rclpy.spin_once(self._node, timeout_sec=0.01)
            except Exception:
                break

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._node is not None:
            try:
                self._node.cmd.publish(Twist())
            except Exception:
                pass
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._node = None
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

    def _estimate(self):
        """Pose estimate: where the episode started, plus odometry since.

        The Gazebo odometry plugin never resets -- after a teleport it keeps
        integrating from wherever it was, with its own accumulated yaw.  Taking
        that pose at face value would hand the policy a different heading offset
        every episode.  Instead the estimate is seeded with the pose read back at
        reset and then advanced by odometry *increments* only, which is what a
        robot that localised once and started driving would have.
        """
        ox, oy, oyaw, _, _ = self._node.odom
        ox0, oy0, oyaw0 = self._odom0
        tx0, ty0, tyaw0 = self._truth0
        c, s = math.cos(-oyaw0), math.sin(-oyaw0)
        rx = (ox - ox0) * c - (oy - oy0) * s
        ry = (ox - ox0) * s + (oy - oy0) * c
        c2, s2 = math.cos(tyaw0), math.sin(tyaw0)
        return (tx0 + rx * c2 - ry * s2,
                ty0 + rx * s2 + ry * c2,
                _wrap(tyaw0 + (oyaw - oyaw0)))

    def _blocked(self, commanded_v, dt):
        """True when the vehicle is commanded forward but is not moving.

        Wheels spin against a wall, so the odometry advances while the simulated
        pose does not.  Four consecutive control periods of that is a contact,
        not a slow start: the vehicle reaches 0.26 m/s in about 1.3 s, and this
        test only fires after 0.4 s of no displacement at all.
        """
        if commanded_v < 0.08:
            self._stuck = 0
            return False
        truth = self._node.truth
        if truth is None:
            return False
        if self._prev_truth is None:
            self._prev_truth = truth
            return False
        moved = math.hypot(truth[0] - self._prev_truth[0], truth[1] - self._prev_truth[1])
        expected = max(abs(commanded_v), 0.05) * dt
        self._prev_truth = truth
        if moved < 0.15 * expected:
            self._stuck += 1
        else:
            self._stuck = 0
        return self._stuck >= 4

    # -- observation -----------------------------------------------------
    def _observe(self):
        scan = self._node.scan
        if scan is None:
            beams = np.ones(SCAN_GROUPS, dtype=np.float32) * SCAN_MAX_M
        else:
            usable = np.where(np.isfinite(scan), scan, SCAN_MAX_M)
            usable = np.clip(usable, 0.0, SCAN_MAX_M)
            beams = usable.reshape(SCAN_GROUPS, SCAN_BEAMS // SCAN_GROUPS).min(axis=1)
        ex, ey, eyaw = self._estimate()
        gx, gy = self._goal_map
        dx, dy = gx - ex, gy - ey
        dist = math.hypot(dx, dy)
        bearing = _wrap(math.atan2(dy, dx) - eyaw)
        obs = np.concatenate([
            beams / SCAN_MAX_M,
            np.array([min(dist / 6.0, 1.0), bearing / math.pi,
                      self._last_action[0] / MAX_V, self._last_action[1] / MAX_W],
                     dtype=np.float32),
        ]).astype(np.float32)
        return obs, dist, bearing

    # -- reset / step ----------------------------------------------------
    def reset(self, goal=None, pose=None):
        self.start()
        self._node.cmd.publish(Twist())
        self._node.wait_sim(0.3)
        report = {}
        target = goal if goal is not None else self.fixed_goal
        if target is None:
            raise ValueError('no goal given')
        where = pose if pose is not None else SPAWN
        report['teleport_accepted'] = teleport(*where)
        self._node.wait_sim(1.2)
        self._node.cmd.publish(Twist())

        # Read the actual pose back instead of trusting the request.
        if self._node.truth is None or self._node.odom is None:
            raise RuntimeError('no pose feedback after reset')
        tx, ty, tyaw = self._node.truth
        ox, oy, oyaw, _, _ = self._node.odom
        report['requested_pose'] = [round(v, 3) for v in where]
        report['settled_truth'] = [round(tx, 4), round(ty, 4), round(tyaw, 4)]
        report['settled_odom'] = [round(ox, 4), round(oy, 4), round(oyaw, 4)]
        report['position_error_m'] = round(math.hypot(tx - where[0], ty - where[1]), 4)

        # Seed the pose estimate with the readback pose; the goal stays in map
        # coordinates and the estimate advances by odometry from here.
        self._odom0 = (ox, oy, oyaw)
        self._truth0 = (tx, ty, tyaw)
        self._goal_map = (float(target[0]), float(target[1]))
        gx, gy = self._goal_map
        self._node.contacts = []
        self._last_action = (0.0, 0.0)
        obs, dist, _ = self._observe()
        self._prev_dist = dist
        self._prev_truth = None
        self._stuck = 0
        self._sim_start = self._node.sim_time
        self._steps = 0
        self._episode += 1
        report['initial_distance_m'] = round(dist, 3)
        report['goal_map'] = [gx, gy]
        self.last_reset_report = report
        info = {'reset': report, 'episode': self._episode}
        return obs, info

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=float).reshape(-1), -1.0, 1.0)
        v = (float(a[0]) + 1.0) * 0.5 * MAX_V
        w = float(a[1]) * MAX_W
        previous_v = self._last_action[0]
        self._last_action = (v, w)
        cmd = Twist()
        cmd.linear.x = v
        cmd.angular.z = w
        self._node.cmd.publish(cmd)

        if not self._node.wait_sim(CONTROL_DT):
            raise RuntimeError('simulated clock did not advance')

        obs, dist, bearing = self._observe()
        # The Gazebo Contact system advertises nothing in this build -- the topic
        # never appears, so "0 collisions" from it would be a measurement that
        # does not exist.  What is available is the disagreement between wheel
        # odometry and the simulated pose: wheels turning while the vehicle does
        # not move means something solid is in the way.
        collisions = _vehicle_contacts(self._node.contacts)
        self._node.contacts = []
        blocked = self._blocked(v, CONTROL_DT)

        terminated = False
        truncated = False
        reason = ''
        reward = 2.0 * (self._prev_dist - dist)          # metres of progress
        reward -= 0.01                                    # one step of time
        reward -= 0.05 * abs(v - previous_v)              # command smoothness
        if self.reward_variant == 'progress_distance':
            reward -= 0.03 * dist                          # idling is not free
        if dist < GOAL_TOL:
            reward += 5.0
            terminated = True
            reason = 'goal'
        elif blocked:
            reward -= 5.0
            terminated = True
            reason = 'collision'
        elif (self._node.sim_time - self._sim_start) >= self.episode_s:
            truncated = True
            reason = 'timeout'
        self._prev_dist = dist
        self._steps += 1
        self._node.cmd.publish(Twist())

        info = {
            'distance_m': round(dist, 3),
            'bearing_rad': round(bearing, 3),
            'collisions': collisions,
            'contact_proxy': blocked,
            'contact_source': 'wheel-odometry versus simulated pose (the Gazebo '
                              'Contact topic is not published in this build)',
            'reason': reason,
            'reward_variant': self.reward_variant,
            'sim_seconds': round(self._node.sim_time - self._sim_start, 2),
            'odom': [round(x, 4) for x in self._node.odom[:3]],
            'truth': [round(x, 4) for x in self._node.truth],
            'goal': self._goal_map,
            'observation_source': 'scan+odometry',
            'truth_used_for': ['teleport', 'success_check', 'collision_check'],
        }
        return obs, float(reward), terminated, truncated, info
