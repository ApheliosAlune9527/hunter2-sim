#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地假 Go2：在 DDS 上发布 LowState/SportModeState，用于无狗时验证订阅链路。

    python3 fake_go2.py --iface lo --domain 1 --seconds 20

注意：这是测试工具，不连接真机；真机 domain 是 0，务必用 --domain 1 与真机隔离。
"""
import argparse
import math
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.default import (
    unitree_go_msg_dds__LowState_,
    unitree_go_msg_dds__SportModeState_,
)
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default="lo")
    ap.add_argument("--domain", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--hz", type=float, default=10.0)
    args = ap.parse_args()

    ChannelFactoryInitialize(args.domain, args.iface)
    low_pub = ChannelPublisher("rt/lowstate", LowState_)
    low_pub.Init()
    sport_pub = ChannelPublisher("rt/sportmodestate", SportModeState_)
    sport_pub.Init()

    low = unitree_go_msg_dds__LowState_()
    sport = unitree_go_msg_dds__SportModeState_()
    low.power_v = 32.4
    low.power_a = -1.2
    low.bms_state.soc = 87
    low.bms_state.status = 1
    low.bms_state.current = -1200
    low.imu_state.temperature = 33
    for i in range(12):
        low.motor_state[i].q = 0.1 * math.sin(i)
        low.motor_state[i].temperature = 35 + i % 4
    low.foot_force[:] = [12, 11, 13, 12]
    sport.mode = 3
    sport.gait_type = 1
    sport.body_height = 0.31
    sport.position[:] = [0.0, 0.0, 0.31]
    sport.velocity[:] = [0.0, 0.0, 0.0]

    print(f"# fake Go2 on domain={args.domain} iface={args.iface} hz={args.hz}", flush=True)
    start = time.time()
    tick = 0
    while time.time() - start < args.seconds:
        low.tick = tick
        low.imu_state.rpy[:] = [0.01 * math.sin(tick / 20.0), 0.01 * math.cos(tick / 20.0), 0.0]
        sport.position[0] = 0.01 * tick
        sport.yaw_speed = 0.05 * math.sin(tick / 10.0)
        low_pub.Write(low)
        sport_pub.Write(sport)
        tick += 1
        time.sleep(1.0 / args.hz)
    print("# done", flush=True)


if __name__ == "__main__":
    main()

