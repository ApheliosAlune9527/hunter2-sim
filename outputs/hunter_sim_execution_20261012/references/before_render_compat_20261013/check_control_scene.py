"""Validate the personal Gazebo control scene using files only."""
import json
import math
import os
from pathlib import Path
import pwd
import re
import xml.etree.ElementTree as ET

from check_ros_isolation import validate_environment


SCENES = Path("/mnt/f/rob-memory/sim/scenes")
WORLD_PLUGINS = {
    ("ignition-gazebo-physics-system", "ignition::gazebo::systems::Physics"),
    ("ignition-gazebo-user-commands-system", "ignition::gazebo::systems::UserCommands"),
    ("ignition-gazebo-scene-broadcaster-system", "ignition::gazebo::systems::SceneBroadcaster"),
}
CONTROLLER = (
    "ignition-gazebo-ackermann-steering-system",
    "ignition::gazebo::systems::AckermannSteering",
)
CONTROL_TEXT = {
    "left_joint": "rear_left_wheel_joint",
    "right_joint": "rear_right_wheel_joint",
    "left_steering_joint": "front_left_steering_joint",
    "right_steering_joint": "front_right_steering_joint",
    "topic": "/hz_sim/cmd_vel",
    "odom_topic": "/hz_sim/odom",
    "tf_topic": "/hz_sim/tf",
    "frame_id": "hz_sim/odom",
    "child_frame_id": "hz_sim/base_link",
}
CONTROL_NUMBERS = {
    "wheel_separation": 0.605, "kingpin_width": 0.605,
    "wheel_base": 0.650, "wheel_radius": 0.165,
    "steering_limit": 0.40,
    "min_velocity": -0.30, "max_velocity": 0.30,
    "min_acceleration": -0.20, "max_acceleration": 0.20,
    "odom_publish_frequency": 30.0,
}


def require(condition, message):
    if not condition:
        raise ValueError("控制场景检查失败：" + message)


def validate_world(root):
    worlds = root.findall("world")
    require(root.tag == "sdf" and len(worlds) == 1, "世界数量错误")
    world = worlds[0]
    require(world.get("name") == "hz_hunter_control", "世界名称错误")
    require(not world.findall(".//include") and not world.findall(".//uri"),
            "不允许外部模型或资源引用")
    world_plugins = world.findall("plugin")
    require(len(world_plugins) == 3 and
            {(p.get("filename"), p.get("name")) for p in world_plugins} == WORLD_PLUGINS,
            "存在非预期世界插件")
    models = world.findall("model")
    require(len(models) == 2 and {m.get("name") for m in models} ==
            {"ground_plane", "hz_hunter_core"}, "存在非预期模型")
    vehicle = world.find("model[@name='hz_hunter_core']")
    plugins = vehicle.findall("plugin")
    require(len(plugins) == 1, "车体仅允许一个已核对的控制器")
    controller = plugins[0]
    require((controller.get("filename"), controller.get("name")) == CONTROLLER,
            "控制器来源错误")
    require(len(world.findall(".//plugin")) == 4, "存在嵌套或其他插件")
    expected = set(CONTROL_TEXT) | set(CONTROL_NUMBERS)
    require(len(controller) == len(expected) and
            {child.tag for child in controller} == expected,
            "控制器参数缺失、重复或包含额外参数")
    for key, value in CONTROL_TEXT.items():
        require(controller.findtext(key) == value, f"{key}不是个人仿真值")
    for key, value in CONTROL_NUMBERS.items():
        actual = float(controller.findtext(key))
        require(math.isfinite(actual) and math.isclose(actual, value, abs_tol=1e-12),
                f"{key}超出本轮核对值")

    wheel_joints = {f"{axle}_{side}_wheel_joint"
                    for axle in ["front", "rear"] for side in ["left", "right"]}
    steer_joints = {f"front_{side}_steering_joint" for side in ["left", "right"]}
    joints = vehicle.findall("joint")
    require(len(vehicle.findall("link")) == 7 and len(joints) == 6 and
            {j.get("name") for j in joints} == wheel_joints | steer_joints,
            "车体结构与已检查骨架不符")

    # Fortress 6.18 uses L/sin(steering_limit), then separate inner/outer angles.
    radius = CONTROL_NUMBERS["wheel_base"] / math.sin(CONTROL_NUMBERS["steering_limit"])
    inner_angle = math.atan(CONTROL_NUMBERS["wheel_base"] /
                           (radius - CONTROL_NUMBERS["kingpin_width"] / 2))
    maximum_wheel_speed = (CONTROL_NUMBERS["max_velocity"] *
                           (1 + CONTROL_NUMBERS["wheel_separation"] / (2 * radius)) /
                           CONTROL_NUMBERS["wheel_radius"])
    for joint in joints:
        name = joint.get("name")
        require(joint.get("type") == "revolute", "关节类型错误")
        axis = [float(value) for value in joint.findtext("axis/xyz").split()]
        if name in steer_joints:
            require(axis == [0, 0, 1], "转向轴错误")
            require(float(joint.findtext("axis/limit/lower")) <= -inner_angle and
                    float(joint.findtext("axis/limit/upper")) >= inner_angle,
                    "转向目标超过单轮关节限位")
        else:
            require(axis == [0, 1, 0], "车轮转轴错误")
            require(float(joint.findtext("axis/limit/velocity")) >= maximum_wheel_speed,
                    "后轮转速可能超过关节速度限位")
    return {
        "world": "hz_hunter_control", "command_topic": CONTROL_TEXT["topic"],
        "odom_topic": CONTROL_TEXT["odom_topic"], "tf_topic": CONTROL_TEXT["tf_topic"],
        "minimum_turning_radius_m": radius,
        "maximum_inner_steering_rad": inner_angle,
        "maximum_rear_wheel_speed_rad_s": maximum_wheel_speed,
        "ros_bridge": False, "hardware_driver": False,
    }


def main():
    validate_environment(os.environ, Path("/proc/sys/kernel/osrelease").read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    require(os.environ.get("IGN_PARTITION") == "hz_sim_aphelios_73" and
            os.environ.get("IGN_IP") == "127.0.0.1" and not os.environ.get("IGN_RELAY"),
            "Gazebo个人分区或公告地址错误")
    report = validate_world(ET.parse(SCENES / "hz_hunter_control.sdf").getroot())
    gui_text = (SCENES / "hz_hunter_preview_gui.config").read_text()
    gui_text = re.sub(r"^\s*<\?xml[^?]*\?>", "", gui_text, count=1)
    gui = ET.fromstring("<hz_gui>" + gui_text + "</hz_gui>")
    require(gui.findtext("plugin[@filename='WorldControl']/start_paused") == "true",
            "GUI未设置初始暂停")
    plugin = Path("/usr/lib/x86_64-linux-gnu/ign-gazebo-6/plugins/"
                  "libignition-gazebo6-ackermann-steering-system.so.6.18.0")
    require(plugin.is_file(), "已核对的Fortress 6.18.0控制插件不存在")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
