#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nav2 / 遥控程序与 Go2 之间的桥：订阅 /cmd_vel，转成 SportClient.Move。

为什么需要它：Go2 没有原生 /cmd_vel；Nav2 输出的是 geometry_msgs/Twist，
必须由本节点限幅、超时停车、再调用高层运动服务。

用法：
    # 实机（先确保已在同一网段，且狗处于站立/可运动状态）
    python3 go2_cmdvel_bridge.py --iface eth0

    # 无狗联调：只打印，不调用 SportClient
    python3 go2_cmdvel_bridge.py --dry-run

安全：
* 限幅 vx ±0.5 / vy ±0.3 / vyaw ±0.8
* 超过 --timeout 秒没有新 /cmd_vel 就 StopMove
* Ctrl-C 退出时 StopMove
* 不碰低层控制；遥控器始终优先
"""
import argparse
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


def clamp(v, lo, hi):
    return max(lo, min(hi, float(v)))


class CmdVelBridge(Node):
    def __init__(self, args):
        super().__init__("go2_cmdvel_bridge")
        self.args = args
        self.last_cmd = 0.0
        self.active = False
        self.client = None
        self.dry = args.dry_run

        if not self.dry:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.sport.sport_client import SportClient

            if args.iface:
                ChannelFactoryInitialize(args.domain, args.iface)
            else:
                ChannelFactoryInitialize(args.domain)
            self.client = SportClient()
            self.client.SetTimeout(3.0)
            self.client.Init()
            self.get_logger().info(f"SportClient ready (iface={args.iface}, domain={args.domain})")
        else:
            self.get_logger().info("dry-run: 不连接机器人，只打印指令")

        self.create_subscription(Twist, args.topic, self.on_cmd, 10)
        self.create_timer(1.0 / args.hz, self.tick)

    def on_cmd(self, msg: Twist):
        vx = clamp(msg.linear.x, -0.5, 0.5)
        vy = clamp(msg.linear.y, -0.3, 0.3)
        vyaw = clamp(msg.angular.z, -0.8, 0.8)
        self.target = (vx, vy, vyaw)
        self.last_cmd = time.time()
        self.active = True

    def tick(self):
        if not self.active:
            return
        age = time.time() - self.last_cmd
        if age > self.args.timeout:
            self.stop("cmd_vel timeout")
            return
        vx, vy, vyaw = self.target
        if self.dry:
            self.get_logger().info(f"[dry] Move({vx:.2f}, {vy:.2f}, {vyaw:.2f})")
        else:
            self.client.Move(vx, vy, vyaw)

    def stop(self, reason=""):
        if not self.active:
            return
        self.active = False
        if self.dry:
            self.get_logger().info(f"[dry] StopMove ({reason})")
        else:
            self.client.StopMove()
            self.get_logger().info(f"StopMove ({reason})")

    def close(self):
        self.stop("shutdown")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default=None)
    ap.add_argument("--domain", type=int, default=0)
    ap.add_argument("--topic", default="/cmd_vel")
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--timeout", type=float, default=0.5, help="多久没收到 cmd_vel 就停")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rclpy.init()
    node = CmdVelBridge(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.close()
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
