#!/usr/bin/env python3
"""Send one ComputePathToPose goal and print the result.

Usage: try_plan.py x y yaw [sx sy syaw]
With start args the request uses an explicit start pose.
"""
import sys
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import ComputePathToPose
from geometry_msgs.msg import PoseStamped

def pose(x, y, yaw):
    p = PoseStamped()
    p.header.frame_id = "map"
    p.pose.position.x = x
    p.pose.position.y = y
    p.pose.orientation.z = math.sin(yaw / 2.0)
    p.pose.orientation.w = math.cos(yaw / 2.0)
    return p

def main():
    x, y, yaw = map(float, sys.argv[1:4])
    rclpy.init()
    node = Node("try_plan")
    client = ActionClient(node, ComputePathToPose, "compute_path_to_pose")
    if not client.wait_for_server(timeout_sec=10.0):
        print("NO_SERVER")
        return
    goal = ComputePathToPose.Goal()
    goal.goal = pose(x, y, yaw)
    goal.goal.header.stamp = node.get_clock().now().to_msg()
    if len(sys.argv) >= 7:
        sx, sy, syaw = map(float, sys.argv[4:7])
        goal.start = pose(sx, sy, syaw)
        goal.start.header.stamp = goal.goal.header.stamp
        goal.use_start = True
        print("start", sx, sy, syaw)
    else:
        goal.use_start = False
    fut = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=10.0)
    handle = fut.result()
    if handle is None or not handle.accepted:
        print("REJECTED")
        return
    rf = handle.get_result_async()
    rclpy.spin_until_future_complete(node, rf, timeout_sec=30.0)
    res = rf.result()
    if res is None:
        print("NO_RESULT")
        return
    path = res.result.path
    print("status", res.status, "poses", len(path.poses))
    if path.poses:
        a, b = path.poses[0].pose.position, path.poses[-1].pose.position
        print("first", a.x, a.y, "last", b.x, b.y)
        length = sum(math.hypot(path.poses[i].pose.position.x - path.poses[i-1].pose.position.x,
                                path.poses[i].pose.position.y - path.poses[i-1].pose.position.y)
                     for i in range(1, len(path.poses)))
        print("length", round(length, 3))
    rclpy.shutdown()

if __name__ == "__main__":
    main()
