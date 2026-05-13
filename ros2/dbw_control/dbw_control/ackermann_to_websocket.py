#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from ackermann_msgs.msg import AckermannDriveStamped


class AckermannToWebsocket(Node):
    def __init__(self):
        super().__init__('ackermann_to_websocket')

        # Topics & timing
        self.declare_parameter('ackermann_topic', '/vehicle_command_ackermann')
        self.declare_parameter('topic', '/to_websocket')
        self.declare_parameter('topic_with_time', '/to_websocket_with_time')
        self.declare_parameter('rate_hz', 20.0)

        # Output shaping
        self.declare_parameter('max_steer_deg', 90.0)   # -90..90 -> -1..1
        self.declare_parameter('throttle', -1.0)        # constant throttle default
        self.declare_parameter('brake_val', -1.0)       # constant brake default

        ack_topic = self.get_parameter('ackermann_topic').value
        topic = self.get_parameter('topic').value
        topic_with_time = self.get_parameter('topic_with_time').value
        self.rate_hz = float(self.get_parameter('rate_hz').value)

        self.max_steer_deg = float(self.get_parameter('max_steer_deg').value)
        self.throttle_val = float(self.get_parameter('throttle').value)
        self.brake_val = float(self.get_parameter('brake_val').value)

        # Latest command from Ackermann topic
        self.latest_steer_norm = None  # [-1, 1]

        # Subscriber
        self.sub = self.create_subscription(
            AckermannDriveStamped,
            ack_topic,
            self._ack_cb,
            10
        )

        # Publishers (JSON for websockets)
        self.pub = self.create_publisher(String, topic, 3)
        self.pub_with_time = self.create_publisher(String, topic_with_time, 3)

        period = 1.0 / max(self.rate_hz, 1e-6)
        self.timer = self.create_timer(period, self._on_timer)

    def _ack_cb(self, msg: AckermannDriveStamped):
        # Ackermann steering_angle is in radians; convert to degrees
        steer_deg = math.degrees(msg.drive.steering_angle)

        # Scale -max..max deg -> -1..1 and clamp
        denom = self.max_steer_deg if abs(self.max_steer_deg) > 1e-9 else 1.0
        steer_norm = steer_deg / denom
        steer_norm = max(-1.0, min(1.0, steer_norm))

        self.latest_steer_norm = steer_norm

    def _on_timer(self):
        # Don't publish until we've received at least one Ackermann message
        if self.latest_steer_norm is None:
            return

        now = self.get_clock().now()
        stamp = now.to_msg()

        steering = -1* self.latest_steer_norm
        brake = self.brake_val

        # Base JSON
        msg = String()
        msg.data = (
            f'{{"control_input": {{"steering": {steering:.2f}, '
            f'"throttle": {self.throttle_val:.2f}, "brake": {brake}}}}}'
        )
        self.pub.publish(msg)

        # JSON including ROS time
        msg2 = String()
        msg2.data = (
            f'{{"control_input": {{"steering": {steering:.2f}, '
            f'"throttle": {self.throttle_val:.2f}, "brake": {brake}}}, '
            f'"ros_time": {{"sec": {stamp.sec}, "nanosec": {stamp.nanosec}}}}}'
        )
        self.pub_with_time.publish(msg2)


def main():
    rclpy.init()
    node = AckermannToWebsocket()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
