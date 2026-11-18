#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Go2 安全速度控制示例（高层 SportClient）。

用法：
    # 不连接机器人，只看会发什么
    python3 go2_move.py --dry-run --vx 0.2 --duration 2

    # 实机：先站起，再以 0.2 m/s 前进 2 秒，然后停
    python3 go2_move.py --iface eth0 --stand --vx 0.2 --duration 2

安全设计：
* 速度限幅：vx ±0.5, vy ±0.3, vyaw ±0.8（远低于 Go2 极限，室内够用）
* 总时长上限 10 s；任何异常/ Ctrl-C 都会 StopMove
* Move 在 SDK 里是 no-reply，必须自己计时并显式 StopMove
* 本脚本不会切换到低层控制；遥控器始终优先，按下遥控器即可接管
"""
import argparse
import sys
import time

MAX_VX, MAX_VY, MAX_VYAW = 0.5, 0.3, 0.8
MAX_DURATION = 10.0

LIMITS = {
    "vx": (-MAX_VX, MAX_VX),
    "vy": (-MAX_VY, MAX_VY),
    "vyaw": (-MAX_VYAW, MAX_VYAW),
}


def clamp(name, value):
    lo, hi = LIMITS[name]
    v = max(lo, min(hi, float(value)))
    if v != float(value):
        print(f"[warn] {name}={value} 超出安全范围，已限幅为 {v}", file=sys.stderr)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default=None)
    ap.add_argument("--domain", type=int, default=0)
    ap.add_argument("--vx", type=float, default=0.0)
    ap.add_argument("--vy", type=float, default=0.0)
    ap.add_argument("--vyaw", type=float, default=0.0)
    ap.add_argument("--duration", type=float, default=1.0)
    ap.add_argument("--hz", type=float, default=10.0, help="重复发送 Move 的频率")
    ap.add_argument("--stand", action="store_true", help="先 StandUp + BalanceStand")
    ap.add_argument("--down", action="store_true", help="结束后 StandDown")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = ap.parse_args()

    vx, vy, vyaw = clamp("vx", args.vx), clamp("vy", args.vy), clamp("vyaw", args.vyaw)
    duration = max(0.1, min(MAX_DURATION, args.duration))
    period = 1.0 / max(1.0, args.hz)

    print(f"plan: Move(vx={vx}, vy={vy}, vyaw={vyaw}) for {duration:.2f}s, then StopMove")
    if args.dry_run:
        print("dry-run: 未连接机器人，未发送任何指令")
        return
    if not args.yes:
        input("确认机器人周围 2 m 内无人、无台阶，且手放在遥控器急停上，按 Enter 继续（Ctrl-C 取消）...")

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize
    from unitree_sdk2py.go2.sport.sport_client import SportClient

    if args.iface:
        ChannelFactoryInitialize(args.domain, args.iface)
    else:
        ChannelFactoryInitialize(args.domain)

    client = SportClient()
    client.SetTimeout(5.0)
    client.Init()

    try:
        if args.stand:
            print("StandUp ->", client.StandUp())
            time.sleep(2.0)
            print("BalanceStand ->", client.BalanceStand())
            time.sleep(0.5)
        print("Move ->", client.Move(vx, vy, vyaw))
        t0 = time.time()
        while time.time() - t0 < duration:
            time.sleep(period)
            # 持续重发，避免底层速度指令过期；返回值只是调用码
            client.Move(vx, vy, vyaw)
    except KeyboardInterrupt:
        print("\ninterrupted")
    finally:
        print("StopMove ->", client.StopMove())
        if args.down:
            time.sleep(0.5)
            print("StandDown ->", client.StandDown())


if __name__ == "__main__":
    main()
