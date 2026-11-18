#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Go2 的 rt/lowstate 录成 CSV，便于离线分析/画图/做数据集。

    python3 go2_record.py --iface eth0 --out run1.csv --seconds 30
    python3 go2_record.py --iface eth0 --domain 1 --out fake.csv --seconds 5   # 配合 fake_go2.py

只订阅，不控制。
"""
import argparse
import csv
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_


FIELDS = (
    ["t_wall", "t_mono", "tick", "power_v", "power_a", "soc", "bms_current", "imu_temp"]
    + ["rpy_r", "rpy_p", "rpy_y"]
    + [f"m{i}_{k}" for i in range(12) for k in ("q", "dq", "tau", "temp")]
    + [f"foot{i}" for i in range(4)]
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default=None)
    ap.add_argument("--domain", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=0, help="0 = 一直录到 Ctrl-C")
    ap.add_argument("--max-hz", type=float, default=0, help="限频保存，0 = 全量")
    args = ap.parse_args()

    if args.iface:
        ChannelFactoryInitialize(args.domain, args.iface)
    else:
        ChannelFactoryInitialize(args.domain)

    f = open(args.out, "w", encoding="utf-8", newline="")
    w = csv.writer(f)
    w.writerow(FIELDS)
    state = {"n": 0, "last": 0.0}

    def on_low(msg):
        now = time.time()
        if args.max_hz and now - state["last"] < 1.0 / args.max_hz:
            return
        state["last"] = now
        row = [
            f"{now:.6f}", f"{time.monotonic():.6f}", int(msg.tick),
            f"{float(msg.power_v):.3f}", f"{float(msg.power_a):.3f}",
            int(msg.bms_state.soc), int(msg.bms_state.current), f"{float(msg.imu_state.temperature):.1f}",
        ]
        row += [f"{float(x):.5f}" for x in msg.imu_state.rpy]
        for i in range(12):
            m = msg.motor_state[i]
            row += [f"{float(m.q):.5f}", f"{float(m.dq):.5f}", f"{float(m.tau_est):.5f}", str(int(m.temperature))]
        row += [str(int(x)) for x in msg.foot_force]
        w.writerow(row)
        state["n"] += 1
        if state["n"] % 100 == 0:
            f.flush()

    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(on_low, 10)

    print(f"# recording {args.out} ... Ctrl-C to stop", flush=True)
    start = time.time()
    try:
        while True:
            time.sleep(0.5)
            if args.seconds and time.time() - start >= args.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        f.flush()
        f.close()
        print(f"# saved {state['n']} rows -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
