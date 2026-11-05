import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
import serial
import struct
import math
import threading
import time

class CH104Publisher(Node):
    def __init__(self):
        super().__init__('ch104_publisher')
        
        self.declare_parameter('port', '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 115200) 
        self.declare_parameter('frame_id', 'imu_link')

        port = self.get_parameter('port').value
        baud = self.get_parameter('baudrate').value
        self.frame_id = self.get_parameter('frame_id').value

        # FAST-LIVO2 需要 Reliable 模式
        self.publisher_ = self.create_publisher(Imu, '/imu/data', 10)

        try:
            self.serial_port = serial.Serial(port, baud, timeout=None)
            self.get_logger().info(f'成功打开串口: {port} 波特率: {baud}')
        except Exception as e:
            self.get_logger().error(f'无法打开串口 {port}: {e}')
            return

        self.running = True
        
        # 独立线程高速读取
        self.read_thread = threading.Thread(target=self.serial_thread_func, daemon=True)
        self.read_thread.start()

    def serial_thread_func(self):
        buffer = bytearray()
        FRAME_LEN = 82
        
        while self.running and rclpy.ok():
            try:
                if not hasattr(self, 'serial_port') or not self.serial_port.is_open:
                    break
                
                # 瞬间清空底层堆积的所有数据
                waiting = self.serial_port.in_waiting or 0
                data = self.serial_port.read(max(1, waiting))
                
                if not data:
                    continue
                buffer.extend(data)
                
                # 内存级快速切割
                while len(buffer) >= FRAME_LEN:
                    head_idx = buffer.find(b'\x5A\xA5')
                    
                    if head_idx == -1:
                        # 全是垃圾数据，保留最后 1 个字节
                        del buffer[:-1]
                        break
                    elif head_idx > 0:
                        # 垃圾数据在包头前面，一刀切掉
                        del buffer[:head_idx]
                        continue
                        
                    # 此时 buffer 头部绝对是一帧完整有效的 82 字节数据
                    frame = buffer[:FRAME_LEN]
                    
                    # 💥 核心修复点：切掉前两字节的 0x5A 0xA5，剩下的 80 字节传给你的解析逻辑
                    self.parse_imu_data(frame[2:])
                    
                    # 极速移除已处理的数据
                    del buffer[:FRAME_LEN]
                            
            except serial.SerialException:
                break
            except Exception as e:
                if self.running:
                    self.get_logger().warn(f'串口读取错误: {e}')
                time.sleep(0.01)

    def parse_imu_data(self, data):
        if data[4] != 0x91:
            return

        msg = Imu()
        # 赋予系统最新时间戳
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        payload = data[4:]
        
        acc_x, acc_y, acc_z = struct.unpack('<fff', payload[12:24])
        msg.linear_acceleration.x = acc_x * 9.81
        msg.linear_acceleration.y = acc_y * 9.81
        msg.linear_acceleration.z = acc_z * 9.81

        gyro_x, gyro_y, gyro_z = struct.unpack('<fff', payload[24:36])
        msg.angular_velocity.x = math.radians(gyro_x)
        msg.angular_velocity.y = math.radians(gyro_y)
        msg.angular_velocity.z = math.radians(gyro_z)

        q_w, q_x, q_y, q_z = struct.unpack('<ffff', payload[60:76])
        msg.orientation.w = q_w
        msg.orientation.x = q_x
        msg.orientation.y = q_y
        msg.orientation.z = q_z

        msg.orientation_covariance = [0.0] * 9
        msg.angular_velocity_covariance = [0.0] * 9
        msg.linear_acceleration_covariance = [0.0] * 9

        self.publisher_.publish(msg)

    def destroy_node(self):
        self.running = False
        if hasattr(self, 'serial_port') and self.serial_port.is_open:
            self.serial_port.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CH104Publisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
