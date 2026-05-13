#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class SmoothWaveToWebsocket(Node):
    """
    Step pattern for y(t):

      idle_start s at y=0
      dur_mid1 s at y=step_mid
      dur_high s at y=step_high
      dur_mid2 s at y=step_mid
      idle_end s at y=0

    Steering is y(t).
    """

    def __init__(self):
        super().__init__('smooth_wave_to_websocket')

        # Topics & timing
        self.declare_parameter('topic', '/to_websocket')
        self.declare_parameter('topic_with_time', '/to_websocket_with_time')
        self.declare_parameter('rate_hz', 20.0)

        # Idle durations (match your request: 5 s before and 5 s after)
        self.declare_parameter('idle_start', 5.0)
        self.declare_parameter('idle_end', 5.0)

        # Step levels (match your request: 0.5 then 1.0 then 0.5)
        self.declare_parameter('step_low', 0.0)
        self.declare_parameter('step_mid', 0.5)
        self.declare_parameter('step_high', 1.0)

        # Step durations (match your request: each 1 s)
        self.declare_parameter('dur_mid1', 2.0)   # 0.5 for 1 s
        self.declare_parameter('dur_high', 2.0)   # 1.0 for 1 s
        self.declare_parameter('dur_mid2', 2.0)   # 0.5 for 1 s

        # Keep repeat support
        self.declare_parameter('repeat', False)

        # Output shaping
        self.declare_parameter('steering_amp', 1)  # scales y
        self.declare_parameter('throttle', -1)       # constant throttle default
        self.declare_parameter('brake_val', -1)      # constant brake default

        topic = self.get_parameter('topic').value
        topic_with_time = self.get_parameter('topic_with_time').value
        self.rate_hz = float(self.get_parameter('rate_hz').value)

        self.idle_start = float(self.get_parameter('idle_start').value)
        self.idle_end = float(self.get_parameter('idle_end').value)

        self.step_low = float(self.get_parameter('step_low').value)
        self.step_mid = float(self.get_parameter('step_mid').value)
        self.step_high = float(self.get_parameter('step_high').value)

        self.dur_mid1 = float(self.get_parameter('dur_mid1').value)
        self.dur_high = float(self.get_parameter('dur_high').value)
        self.dur_mid2 = float(self.get_parameter('dur_mid2').value)

        self.repeat = bool(self.get_parameter('repeat').value)

        self.steering_amp = float(self.get_parameter('steering_amp').value)
        self.throttle_val = float(self.get_parameter('throttle').value)
        self.brake_val = float(self.get_parameter('brake_val').value)

        # Segment boundaries for the step pattern
        self.tA = self.idle_start                    # start of first plateau (mid)
        self.tB = self.tA + self.dur_mid1            # start of high plateau
        self.tC = self.tB + self.dur_high            # start of second mid plateau
        self.tD = self.tC + self.dur_mid2            # start of trailing idle
        self.T_total = self.tD + self.idle_end       # full pattern length

        # Publishers
        self.pub = self.create_publisher(String, topic, 3)
        self.pub_with_time = self.create_publisher(String, topic_with_time, 3)

        self.t0 = self.get_clock().now()
        period = 1.0 / max(self.rate_hz, 1e-6)
        self.timer = self.create_timer(period, self._on_timer)

    def _y_of_t(self, t: float) -> float:
        """Return step value according to the specified schedule."""
        # Optionally loop the pattern
        if self.repeat and self.T_total > 0.0:
            t = t % self.T_total

        if t < self.idle_start:
            return self.step_low  # 0
        if t < self.tB:
            return self.step_mid  # 0.5
        if t < self.tC:
            return self.step_high # 1.0
        if t < self.tD:
            return self.step_mid  # 0.5
        if t <= self.T_total:
            return self.step_low  # 0

        return self.step_low

    def _on_timer(self):
        now = self.get_clock().now()
        t = (now - self.t0).nanoseconds * 1e-9
        y = self._y_of_t(t)                 # y ∈ {0, 0.5, 1, 0.5, 0}
        steering = self.steering_amp * y    # scale if desired

        brake = self.brake_val

        # Base JSON
        msg = String()
        msg.data = (
            f'{{"control_input": {{"steering": {steering:.2f}, '
            f'"throttle": {self.throttle_val:.2f}, "brake": {brake}}}}}'
        )
        self.pub.publish(msg)

        # JSON including ROS time
        stamp = now.to_msg()
        msg2 = String()
        msg2.data = (
            f'{{"control_input": {{"steering": {steering:.2f}, '
            f'"throttle": {self.throttle_val:.2f}, "brake": {brake}}}, '
            f'"ros_time": {{"sec": {stamp.sec}, "nanosec": {stamp.nanosec}}}}}'
        )
        self.pub_with_time.publish(msg2)

def main():
    rclpy.init()
    node = SmoothWaveToWebsocket()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
