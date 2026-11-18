import time, rclpy
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
rclpy.init(args=[])
n = rclpy.create_node("qos_test")
counts = {"clock_default": 0, "clock_sensor": 0, "scan_default": 0, "scan_sensor": 0}
n.create_subscription(Clock, "/clock", lambda m: counts.__setitem__("clock_default", counts["clock_default"]+1), 10)
n.create_subscription(Clock, "/clock", lambda m: counts.__setitem__("clock_sensor", counts["clock_sensor"]+1), qos_profile_sensor_data)
n.create_subscription(LaserScan, "/scan", lambda m: counts.__setitem__("scan_default", counts["scan_default"]+1), 10)
n.create_subscription(LaserScan, "/scan", lambda m: counts.__setitem__("scan_sensor", counts["scan_sensor"]+1), qos_profile_sensor_data)
end = time.monotonic() + 8
while time.monotonic() < end:
    rclpy.spin_once(n, timeout_sec=0.1)
print(counts)
n.destroy_node(); rclpy.shutdown()
