#!/usr/bin/env python3
"""
Simple ROS2 bridge: reads CSV lines from serial and publishes IMU + gait topics.

Expected CSV from device (new firmware):
time_ms,th_qw,th_qx,th_qy,th_qz,th_ax_g,th_ay_g,th_az_g,th_gx_dps,th_gy_dps,th_gz_dps,
sh_qw,sh_qx,sh_qy,sh_qz,sh_ax_g,sh_ay_g,sh_az_g,sh_gx_dps,sh_gy_dps,sh_gz_dps,knee_deg,force_raw,stance
"""
import argparse
import math
import sys
import time

import serial

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32, Int32, Bool


class SerialBridge(Node):
    def __init__(self, port, baud):
        super().__init__('gait_serial_bridge')
        self.port = port
        self.baud = baud
        self.ser = serial.Serial(port, baud, timeout=1)

        self.pub_thigh = self.create_publisher(Imu, 'imu/thigh', 10)
        self.pub_shank = self.create_publisher(Imu, 'imu/shank', 10)
        self.pub_knee = self.create_publisher(Float32, 'knee_angle', 10)
        self.pub_force = self.create_publisher(Int32, 'force_raw', 10)
        self.pub_stance = self.create_publisher(Bool, 'stance', 10)

        self.get_logger().info(f'Opened serial {port} @ {baud}')

    def run(self):
        while rclpy.ok():
            try:
                line = self.ser.readline().decode('utf-8').strip()
            except Exception as e:
                self.get_logger().error(f'Serial read error: {e}')
                time.sleep(0.1)
                continue

            if not line:
                continue

            # skip header lines or non-CSV
            if any(h in line.lower() for h in ('time_ms', 'thigh')):
                continue

            parts = line.split(',')
            if len(parts) < 6:
                self.get_logger().debug(f'Bad CSV: {line}')
                continue

            try:
                t_ms = int(parts[0])
                # parse thigh quaternion + accel(g) + gyro(dps)
                thigh_qw = float(parts[1]); thigh_qx = float(parts[2]); thigh_qy = float(parts[3]); thigh_qz = float(parts[4])
                thigh_ax_g = float(parts[5]); thigh_ay_g = float(parts[6]); thigh_az_g = float(parts[7])
                thigh_gx_dps = float(parts[8]); thigh_gy_dps = float(parts[9]); thigh_gz_dps = float(parts[10])
                # parse shank quaternion + accel + gyro
                shank_qw = float(parts[11]); shank_qx = float(parts[12]); shank_qy = float(parts[13]); shank_qz = float(parts[14])
                shank_ax_g = float(parts[15]); shank_ay_g = float(parts[16]); shank_az_g = float(parts[17])
                shank_gx_dps = float(parts[18]); shank_gy_dps = float(parts[19]); shank_gz_dps = float(parts[20])
                knee_flexion_deg = float(parts[21])
                force_raw = int(parts[22])
                stance = bool(int(parts[23]))
            except Exception as e:
                self.get_logger().warning(f'Parse error: {e} -- {line}')
                continue

            # Create IMU messages using provided quaternion + gyro/accel
            thigh_msg = Imu()
            shank_msg = Imu()

            # Set header with timestamp and frame_id
            now = self.get_clock().now().to_msg()
            thigh_msg.header.stamp = now
            thigh_msg.header.frame_id = 'imu_thigh_link'
            shank_msg.header.stamp = now
            shank_msg.header.frame_id = 'imu_shank_link'

            thigh_msg.orientation.w = thigh_qw
            thigh_msg.orientation.x = thigh_qx
            thigh_msg.orientation.y = thigh_qy
            thigh_msg.orientation.z = thigh_qz

            shank_msg.orientation.w = shank_qw
            shank_msg.orientation.x = shank_qx
            shank_msg.orientation.y = shank_qy
            shank_msg.orientation.z = shank_qz

            # angular velocity in rad/s (dps -> rad/s)
            d2r = math.pi / 180.0
            thigh_msg.angular_velocity.x = thigh_gx_dps * d2r
            thigh_msg.angular_velocity.y = thigh_gy_dps * d2r
            thigh_msg.angular_velocity.z = thigh_gz_dps * d2r

            shank_msg.angular_velocity.x = shank_gx_dps * d2r
            shank_msg.angular_velocity.y = shank_gy_dps * d2r
            shank_msg.angular_velocity.z = shank_gz_dps * d2r

            # linear acceleration: convert g -> m/s^2
            g = 9.80665
            thigh_msg.linear_acceleration.x = thigh_ax_g * g
            thigh_msg.linear_acceleration.y = thigh_ay_g * g
            thigh_msg.linear_acceleration.z = thigh_az_g * g

            shank_msg.linear_acceleration.x = shank_ax_g * g
            shank_msg.linear_acceleration.y = shank_ay_g * g
            shank_msg.linear_acceleration.z = shank_az_g * g

            self.pub_thigh.publish(thigh_msg)
            self.pub_shank.publish(shank_msg)

            km = Float32()
            km.data = float(knee_flexion_deg)
            self.pub_knee.publish(km)

            fr = Int32()
            fr.data = int(force_raw)
            self.pub_force.publish(fr)

            st = Bool()
            st.data = bool(stance)
            self.pub_stance.publish(st)


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='Serial port (e.g. /dev/ttyUSB0 or COM3)')
    parser.add_argument('--baud', type=int, default=115200)
    args = parser.parse_args(argv)

    rclpy.init()
    node = SerialBridge(args.port, args.baud)
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info('Shutting down')
        node.ser.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
