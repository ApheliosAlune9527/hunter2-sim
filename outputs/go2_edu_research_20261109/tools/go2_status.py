#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Go2 只读状态查看器（不发送任何控制指令）。

用法（在已安装 unitree_sdk2_python、与狗同一网段的 Ubuntu 上）：
    python3 go2_status.py --iface eth0
    python3 go2_status.py --iface eth0 --seconds 10 --json
    python3 go2_status.py --iface lo --domain 1     # 配合 unitree_mujoco 仿真

安全说明：本脚本只订阅 rt/lowstate 与 rt/sportmodestate（遥控器数据在 lowstate 的
wireless_remote 字段里），不会发布 rt/lowcmd 或 rt/api/sport/request，因此不会让狗动。
"""
import argparse
import json
import struct
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_, SportModeState_


MODE_NAMES = {
    0: "idle", 1: "balanceStand", 2: "pose", 3: "locomotion", 4: "reserve",
    5: "lieDown", 6: "jointLock", 7: "damping", 8: "recoveryStand", 9: "reserve",
    10: "sit", 11: "frontFlip", 12: "frontJump", 13: "frontPounce",
}
GAIT_NAMES = {0: "idle", 1: "trot", 2: "run", 3: "climbStair", 4: "forwardDownStair", 9: "adjust"}


class State:
    def __init__(self):
        self.low = None
        self.sport = None
        self.low_count = 0
        self.sport_count = 0
        self.last_low_wall = None
        self.last_sport_wall = None


def fmt_vec(v, n=3, prec=3):
    return "[" + ", ".join(f"{float(x):.{prec}f}" for x in v[:n]) + "]"


def summarize(st: State):
    out = {}
    if st.low is not None:
        low = st.low
        bms = low.bms_state
        temps = [int(m.temperature) for m in low.motor_state]
        out["lowstate"] = {
            "power_v": round(float(low.power_v), 2),
            "power_a": round(float(low.power_a), 2),
            "soc": int(bms.soc),
            "bms_status": int(bms.status),
            "bms_current": int(bms.current),
            "rpy_deg": [round(float(x) * 57.29578, 2) for x in low.imu_state.rpy],
            "imu_temp": round(float(low.imu_state.temperature), 1),
            "max_motor_temp": max(temps) if temps else None,
            "motor_temps": temps,
            "foot_force": [int(x) for x in low.foot_force],
            "tick": int(low.tick),
            "rate_hz": round(st.low_count / max(1e-6, time.time() - st.t0), 1),
        }
    if st.sport is not None:
        s = st.sport
        out["sportmode"] = {
            "mode": int(s.mode),
            "mode_name": MODE_NAMES.get(int(s.mode), "?"),
            "gait_type": int(s.gait_type),
            "gait_name": GAIT_NAMES.get(int(s.gait_type), "?"),
            "position": [round(float(x), 3) for x in s.position],
            "body_height": round(float(s.body_height), 3),
            "velocity": [round(float(x), 3) for x in s.velocity],
            "yaw_speed": round(float(s.yaw_speed), 3),
            "error_code": int(s.error_code),
            "foot_force": [int(x) for x in s.foot_force],
        }
    if st.low is not None:
        raw = bytes(st.low.wireless_remote)
        if len(raw) >= 24:
            out["wireless"] = {
                "lx": round(struct.unpack("<f", raw[4:8])[0], 2),
                "rx": round(struct.unpack("<f", raw[8:12])[0], 2),
                "ry": round(struct.unpack("<f", raw[12:16])[0], 2),
                "ly": round(struct.unpack("<f", raw[20:24])[0], 2),
                "btn1": raw[2],
                "btn2": raw[3],
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default=None, help="连接机器人的网卡名，如 eth0 / enp3s0；仿真用 lo")
    ap.add_argument("--domain", type=int, default=0, help="DDS domain id，真机 0，unitree_mujoco 默认 1")
    ap.add_argument("--seconds", type=float, default=0, help="运行时长，0 表示一直运行")
    ap.add_argument("--json", action="store_true", help="输出 JSON，便于记录")
    args = ap.parse_args()

    ChannelFactoryInitialize(args.domain, args.iface) if args.iface else ChannelFactoryInitialize(args.domain)

    st = State()
    st.t0 = time.time()

    def on_low(msg):
        st.low = msg
        st.low_count += 1
        st.last_low_wall = time.time()

    def on_sport(msg):
        st.sport = msg
        st.sport_count += 1
        st.last_sport_wall = time.time()

    def on_remote(msg):
        st.remote = msg

    sub_low = ChannelSubscriber("rt/lowstate", LowState_)
    sub_low.Init(on_low, 10)
    sub_sport = ChannelSubscriber("rt/sportmodestate", SportModeState_)
    sub_sport.Init(on_sport, 10)

    print(f"# listening on domain={args.domain} iface={args.iface or 'default'} ...", flush=True)
    warned = False
    start = time.time()
    try:
        while True:
            time.sleep(1.0)
            elapsed = time.time() - start
            if st.low is None and not warned and elapsed > 3:
                warned = True
                print("# 3 秒内没有收到 rt/lowstate：检查网卡名、网线、ROS_DOMAIN_ID/domain、防火墙；"
                      "真机 domain=0，仿真 domain=1", file=sys.stderr, flush=True)
            data = summarize(st)
            if args.json:
                print(json.dumps({"t": round(elapsed, 2), **data}, ensure_ascii=False), flush=True)
            else:
                print(f"--- t={elapsed:6.1f}s low={st.low_count} sport={st.sport_count}", flush=True)
                if "lowstate" in data:
                    d = data["lowstate"]
                    print(f"  battery {d['soc']}% {d['power_v']}V {d['power_a']}A | "
                          f"rpy {d['rpy_deg']} | imu {d['imu_temp']}C | motor_max {d['max_motor_temp']}C | "
                          f"foot {d['foot_force']} | low_hz {d['rate_hz']}", flush=True)
                if "sportmode" in data:
                    d = data["sportmode"]
                    print(f"  mode {d['mode']}({d['mode_name']}) gait {d['gait_type']}({d['gait_name']}) | "
                          f"pos {d['position']} h {d['body_height']} | vel {d['velocity']} yaw {d['yaw_speed']} | "
                          f"err {d['error_code']}", flush=True)
                if "wireless" in data:
                    d = data["wireless"]
                    print(f"  remote lx {d['lx']} ly {d['ly']} rx {d['rx']} ry {d['ry']} btn {d['btn1']:02x}/{d['btn2']:02x}", flush=True)
            if args.seconds and elapsed >= args.seconds:
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
