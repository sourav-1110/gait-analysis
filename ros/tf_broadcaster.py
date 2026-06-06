#!/usr/bin/env python3
"""
TF broadcaster with ankle capture-on-stance behaviour.

Subscribes:
 - /imu/thigh (sensor_msgs/Imu)
 - /imu/shank (sensor_msgs/Imu)
 - /knee_angle (std_msgs/Float32)
 - /stance (std_msgs/Bool)

Publishes TF frames: hip, thigh, shank, ankle. Ankle can be captured and held in world when stance==True.
"""
import argparse
import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32, Bool
from sensor_msgs.msg import JointState

from geometry_msgs.msg import TransformStamped
import tf_transformations
import tf2_ros


def quat_inverse(q):
    w, x, y, z = q
    norm2 = w*w + x*x + y*y + z*z
    if norm2 == 0.0:
        return (1.0, 0.0, 0.0, 0.0)
    return (w / norm2, -x / norm2, -y / norm2, -z / norm2)


def quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    w = aw*bw - ax*bx - ay*by - az*bz
    x = aw*bx + ax*bw + ay*bz - az*by
    y = aw*by - ax*bz + ay*bw + az*bx
    z = aw*bz + ax*by - ay*bx + az*bw
    return (w, x, y, z)


class TFBroadcaster(Node):
    def __init__(self, thigh_trans, shank_trans, thigh_rot_rpy, shank_rot_rpy,
                 ankle_trans, ankle_rot_rpy, ankle_mode, rate):
        super().__init__('gait_tf_broadcaster')

        self.thigh_trans = tuple(float(x) for x in thigh_trans)
        self.shank_trans = tuple(float(x) for x in shank_trans)
        self.ankle_trans = tuple(float(x) for x in ankle_trans)
        self.rate = float(rate)
        self.ankle_mode = ankle_mode

        def rpy_to_quat_deg(rpy_deg):
            r = math.radians(rpy_deg[0]); p = math.radians(rpy_deg[1]); y = math.radians(rpy_deg[2])
            q = tf_transformations.quaternion_from_euler(r, p, y)
            return (q[3], q[0], q[1], q[2])

        self.thigh_rot_offset = rpy_to_quat_deg(thigh_rot_rpy)
        self.shank_rot_offset = rpy_to_quat_deg(shank_rot_rpy)
        self.ankle_rot_offset = rpy_to_quat_deg(ankle_rot_rpy)

        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.sub_thigh = self.create_subscription(Imu, 'imu/thigh', self.cb_thigh, 10)
        self.sub_shank = self.create_subscription(Imu, 'imu/shank', self.cb_shank, 10)
        self.sub_knee = self.create_subscription(Float32, 'knee_angle', self.cb_knee, 10)
        self.sub_stance = self.create_subscription(Bool, 'stance', self.cb_stance, 10)

        self.joint_pub = self.create_publisher(JointState, 'joint_states', 10)

        self.thigh_q = None
        self.shank_q = None
        self.knee_deg = 0.0

        # stance state and captured ankle pose
        self.stance = False
        self.prev_stance = False
        self.ankle_fixed_pose = None  # (trans, quat) in hip frame

        self.timer = self.create_timer(1.0 / self.rate, self.on_timer)
        self.get_logger().info(f'TF broadcaster started: ankle_mode={self.ankle_mode} rate={self.rate}')

    def cb_thigh(self, msg: Imu):
        self.thigh_q = (msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z)

    def cb_shank(self, msg: Imu):
        self.shank_q = (msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z)

    def cb_knee(self, msg: Float32):
        self.knee_deg = float(msg.data)

    def cb_stance(self, msg: Bool):
        self.stance = bool(msg.data)

    def publish_tf(self, parent_frame, child_frame, trans, quat):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame
        t.transform.translation.x = trans[0]
        t.transform.translation.y = trans[1]
        t.transform.translation.z = trans[2]
        t.transform.rotation.w = quat[0]
        t.transform.rotation.x = quat[1]
        t.transform.rotation.y = quat[2]
        t.transform.rotation.z = quat[3]
        self.tf_broadcaster.sendTransform(t)

    def rotate_vector(self, quat, vec):
        # rotate vector `vec` by quaternion `quat` (w,x,y,z)
        qw, qx, qy, qz = quat
        vw, vx, vy, vz = 0.0, vec[0], vec[1], vec[2]
        f_w = qw*vw - qx*vx - qy*vy - qz*vz
        f_x = qw*vx + qx*vw + qy*vz - qz*vy
        f_y = qw*vy - qx*vz + qy*vw + qz*vx
        f_z = qw*vz + qx*vy - qy*vx + qz*vw
        nq_w, nq_x, nq_y, nq_z = qw, -qx, -qy, -qz
        r_x = f_w*nq_x + f_x*nq_w + f_y*nq_z - f_z*nq_y
        r_y = f_w*nq_y - f_x*nq_z + f_y*nq_w + f_z*nq_x
        r_z = f_w*nq_z + f_x*nq_y - f_y*nq_x + f_z*nq_w
        return (r_x, r_y, r_z)

    def on_timer(self):
        now = self.get_clock().now().to_msg()

        # publish hip->thigh
        if self.thigh_q is not None:
            thigh_total = quat_mul(self.thigh_rot_offset, self.thigh_q)
            self.publish_tf('hip', 'thigh', self.thigh_trans, thigh_total)

        # publish thigh->shank
        if self.thigh_q is not None and self.shank_q is not None:
            shank_total = quat_mul(self.shank_rot_offset, self.shank_q)
            inv_th = quat_inverse(quat_mul(self.thigh_rot_offset, self.thigh_q))
            rel = quat_mul(inv_th, shank_total)
            self.publish_tf('thigh', 'shank', self.shank_trans, rel)

        # publish joint_states
        js = JointState()
        js.header.stamp = now
        js.name = ['knee_joint']
        js.position = [math.radians(self.knee_deg)]
        js.velocity = [0.0]
        js.effort = [0.0]
        self.joint_pub.publish(js)

        # ANKLE modes
        # compute world poses when needed
        if self.ankle_mode == 'follow_shank':
            if self.shank_q is not None:
                ankle_total = quat_mul(self.ankle_rot_offset, self.shank_q)
                self.publish_tf('shank', 'ankle', self.ankle_trans, ankle_total)

        elif self.ankle_mode == 'fixed_always':
            # capture once if not captured
            if self.ankle_fixed_pose is None and self.shank_q is not None and self.thigh_q is not None:
                thigh_total = quat_mul(self.thigh_rot_offset, self.thigh_q)
                shank_total = quat_mul(self.shank_rot_offset, self.shank_q)
                v = [self.thigh_trans[0], self.thigh_trans[1], self.thigh_trans[2]]
                r_shank = self.rotate_vector(thigh_total, self.shank_trans)
                v[0] += r_shank[0]; v[1] += r_shank[1]; v[2] += r_shank[2]
                r_ankle = self.rotate_vector(shank_total, self.ankle_trans)
                v[0] += r_ankle[0]; v[1] += r_ankle[1]; v[2] += r_ankle[2]
                ankle_world_q = quat_mul(shank_total, self.ankle_rot_offset)
                self.ankle_fixed_pose = (tuple(v), ankle_world_q)
            if self.ankle_fixed_pose is not None:
                self.publish_tf('hip', 'ankle', self.ankle_fixed_pose[0], self.ankle_fixed_pose[1])

        elif self.ankle_mode == 'capture_on_stance':
            # detect rising edge of stance
            if (not self.prev_stance) and self.stance and self.shank_q is not None and self.thigh_q is not None:
                thigh_total = quat_mul(self.thigh_rot_offset, self.thigh_q)
                shank_total = quat_mul(self.shank_rot_offset, self.shank_q)
                v = [self.thigh_trans[0], self.thigh_trans[1], self.thigh_trans[2]]
                r_shank = self.rotate_vector(thigh_total, self.shank_trans)
                v[0] += r_shank[0]; v[1] += r_shank[1]; v[2] += r_shank[2]
                r_ankle = self.rotate_vector(shank_total, self.ankle_trans)
                v[0] += r_ankle[0]; v[1] += r_ankle[1]; v[2] += r_ankle[2]
                ankle_world_q = quat_mul(shank_total, self.ankle_rot_offset)
                self.ankle_fixed_pose = (tuple(v), ankle_world_q)

            if self.stance and self.ankle_fixed_pose is not None:
                self.publish_tf('hip', 'ankle', self.ankle_fixed_pose[0], self.ankle_fixed_pose[1])
            else:
                if self.shank_q is not None:
                    ankle_total = quat_mul(self.ankle_rot_offset, self.shank_q)
                    self.publish_tf('shank', 'ankle', self.ankle_trans, ankle_total)

        self.prev_stance = self.stance


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--thigh-trans', nargs=3, type=float, default=[0.0, -0.40, 0.0])
    parser.add_argument('--shank-trans', nargs=3, type=float, default=[0.0, -0.40, 0.0])
    parser.add_argument('--thigh-rot-rpy', nargs=3, type=float, default=[0.0, 0.0, 0.0])
    parser.add_argument('--shank-rot-rpy', nargs=3, type=float, default=[0.0, 0.0, 0.0])
    parser.add_argument('--ankle-trans', nargs=3, type=float, default=[0.01801, 0.00601, 0.0])
    parser.add_argument('--ankle-rot-rpy', nargs=3, type=float, default=[0.0, 0.0, 0.0])
    parser.add_argument('--ankle-mode', choices=['follow_shank', 'fixed_always', 'capture_on_stance'], default='capture_on_stance')
    parser.add_argument('--rate', type=float, default=50.0)
    args = parser.parse_args(argv)

    rclpy.init()
    node = TFBroadcaster(thigh_trans=args.thigh_trans, shank_trans=args.shank_trans,
                         thigh_rot_rpy=args.thigh_rot_rpy, shank_rot_rpy=args.shank_rot_rpy,
                         ankle_trans=args.ankle_trans, ankle_rot_rpy=args.ankle_rot_rpy,
                         ankle_mode=args.ankle_mode, rate=args.rate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
ROS2 TF broadcaster for gait 3D twin.

Listens to `/imu/thigh`, `/imu/shank` (sensor_msgs/Imu) and `/knee_angle` (std_msgs/Float32).
Publishes TF frames:
 - `hip` (fixed)
 - `thigh` (child of hip, orientation from `/imu/thigh`)
 - `shank` (child of thigh, orientation relative computed from `/imu/thigh` and `/imu/shank`)

Also publishes `sensor_msgs/JointState` with `knee_joint` position (radians) so RViz/robot_state_publisher can animate a URDF/mesh skeleton.

Parameters (CLI args):
 --thigh-len, --shank-len (meters) to set translations between joints.
"""
import argparse
import math
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32
from sensor_msgs.msg import JointState

from geometry_msgs.msg import TransformStamped
import tf_transformations
import tf2_ros


def quat_inverse(q):
    w, x, y, z = q
    norm2 = w*w + x*x + y*y + z*z
    if norm2 == 0.0:
        return (1.0, 0.0, 0.0, 0.0)
    return (w / norm2, -x / norm2, -y / norm2, -z / norm2)


def quat_mul(a, b):
    # a * b
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    w = aw*bw - ax*bx - ay*by - az*bz
    x = aw*bx + ax*bw + ay*bz - az*by
    y = aw*by - ax*bz + ay*bw + az*bx
    z = aw*bz + ax*by - ay*bx + az*bw
    return (w, x, y, z)


class TFBroadcaster(Node):
    def __init__(self, thigh_trans=(0.0, -0.40, 0.0), shank_trans=(0.0, -0.40, 0.0),
                 thigh_rot_rpy=(0.0, 0.0, 0.0), shank_rot_rpy=(0.0, 0.0, 0.0), rate=50.0):
                super().__init__('gait_tf_broadcaster')
                self.thigh_trans = tuple(float(x) for x in thigh_trans)
                self.shank_trans = tuple(float(x) for x in shank_trans)
                self.ankle_trans = tuple(float(x) for x in (0.01801, 0.00601, 0.0))
                self.ankle_rot_offset = rpy_to_quat_deg((0.0, 0.0, 0.0))
                self.ankle_mode = 'capture_on_stance'
                self.rate = float(rate)

        # rotation offsets expressed as roll,pitch,yaw in degrees; convert to quaternion
        def rpy_to_quat_deg(rpy_deg):
            r = math.radians(rpy_deg[0]); p = math.radians(rpy_deg[1]); y = math.radians(rpy_deg[2])
            q = tf_transformations.quaternion_from_euler(r, p, y)
            return (q[3], q[0], q[1], q[2]) if len(q) == 4 else (1.0, 0.0, 0.0, 0.0)

                self.thigh_rot_offset = rpy_to_quat_deg(thigh_rot_rpy)
                self.shank_rot_offset = rpy_to_quat_deg(shank_rot_rpy)
                self.ankle_rot_offset = rpy_to_quat_deg((0.0, 0.0, 0.0))
                self.ankle_mode = 'capture_on_stance'

        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.sub_thigh = self.create_subscription(Imu, 'imu/thigh', self.cb_thigh, 10)
        self.sub_shank = self.create_subscription(Imu, 'imu/shank', self.cb_shank, 10)
        self.sub_knee = self.create_subscription(Float32, 'knee_angle', self.cb_knee, 10)

        self.joint_pub = self.create_publisher(JointState, 'joint_states', 10)

        self.thigh_q = None
        self.shank_q = None
        self.knee_deg = 0.0

        self.timer = self.create_timer(1.0 / self.rate, self.on_timer)

        self.get_logger().info(f'TF broadcaster started: thigh_trans={self.thigh_trans} shank_trans={self.shank_trans} rate={self.rate}')

    def cb_thigh(self, msg: Imu):
        self.thigh_q = (msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z)

    def cb_shank(self, msg: Imu):
        self.shank_q = (msg.orientation.w, msg.orientation.x, msg.orientation.y, msg.orientation.z)

    def cb_knee(self, msg: Float32):
        self.knee_deg = float(msg.data)

    def publish_tf(self, parent_frame, child_frame, trans, quat):
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = parent_frame
        t.child_frame_id = child_frame
        t.transform.translation.x = trans[0]
        t.transform.translation.y = trans[1]
        t.transform.translation.z = trans[2]
        t.transform.rotation.w = quat[0]
        t.transform.rotation.x = quat[1]
        t.transform.rotation.y = quat[2]
        t.transform.rotation.z = quat[3]
        self.tf_broadcaster.sendTransform(t)

    def on_timer(self):
        # hip is fixed at origin
        # publish hip frame as identity (optional)
        now = self.get_clock().now().to_msg()

        if self.thigh_q is not None:
            # apply configured rotation offset to thigh quaternion
            thigh_total = quat_mul(self.thigh_rot_offset, self.thigh_q)
            self.publish_tf('hip', 'thigh', self.thigh_trans, thigh_total)

        if self.thigh_q is not None and self.shank_q is not None:
            # apply configured rotation offset to shank quaternion
            shank_total = quat_mul(self.shank_rot_offset, self.shank_q)
            # compute relative rotation: inv(thigh_total) * shank_total
            inv_th = quat_inverse(quat_mul(self.thigh_rot_offset, self.thigh_q))
            rel = quat_mul(inv_th, shank_total)
            self.publish_tf('thigh', 'shank', self.shank_trans, rel)

        # publish joint_states with knee angle (in radians)
        js = JointState()
        js.header.stamp = now
        js.header.frame_id = 'world'
        js.name = ['knee_joint']
        js.position = [math.radians(self.knee_deg)]
        js.velocity = [0.0]  # not computed; set to 0
        js.effort = [0.0]    # effort not available
        self.joint_pub.publish(js)

    def cb_stance(self, msg: Bool):
        self.stance = bool(msg.data)

    def rotate_vector(self, quat, vec):
        # rotate vector `vec` by quaternion `quat` (w,x,y,z)
        # v' = q * (0, v) * q_conj
        qw, qx, qy, qz = quat
        # q * v
        # treat v as quaternion (0, vx, vy, vz)
        vw, vx, vy, vz = 0.0, vec[0], vec[1], vec[2]
        # first = q * v
        f_w = qw*vw - qx*vx - qy*vy - qz*vz
        f_x = qw*vx + qx*vw + qy*vz - qz*vy
        f_y = qw*vy - qx*vz + qy*vw + qz*vx
        f_z = qw*vz + qx*vy - qy*vx + qz*vw
        # q_conj
        nq_w, nq_x, nq_y, nq_z = qw, -qx, -qy, -qz
        # result = first * q_conj
        r_x = f_w*nq_x + f_x*nq_w + f_y*nq_z - f_z*nq_y
        r_y = f_w*nq_y - f_x*nq_z + f_y*nq_w + f_z*nq_x
        r_z = f_w*nq_z + f_x*nq_y - f_y*nq_x + f_z*nq_w
        return (r_x, r_y, r_z)

def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument('--thigh-trans', nargs=3, type=float, default=[0.0, -0.40, 0.0],
                        help='Translation vector for hip->thigh (x y z) in meters')
    parser.add_argument('--shank-trans', nargs=3, type=float, default=[0.0, -0.40, 0.0],
                        help='Translation vector for thigh->shank (x y z) in meters')
    parser.add_argument('--thigh-rot-rpy', nargs=3, type=float, default=[0.0, 0.0, 0.0],
                        help='Rotation offset for thigh IMU as roll pitch yaw in degrees')
    parser.add_argument('--shank-rot-rpy', nargs=3, type=float, default=[0.0, 0.0, 0.0],
                        help='Rotation offset for shank IMU as roll pitch yaw in degrees')
    parser.add_argument('--rate', type=float, default=50.0)
    args = parser.parse_args(argv)

    rclpy.init()
    node = TFBroadcaster(thigh_trans=args.thigh_trans, shank_trans=args.shank_trans,
                         thigh_rot_rpy=args.thigh_rot_rpy, shank_rot_rpy=args.shank_rot_rpy,
                         rate=args.rate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
