#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class BrakeStepPublisher(Node):
    """
    Publishes JSON:
      {"control_input": {"steering": <const>, "throttle": <const>, "brake": <value>}}

    Step profile for brake(t):
      - hold brake_low   for t_low_start seconds
      - jump to brake_high and hold for t_high_hold seconds
      - jump back to brake_low and hold for t_low_end seconds
    """

    def __init__(self):
        super().__init__('brake_step_publisher')

        # -------- Parameters --------
        self.declare_parameter('topic', '/to_websocket')
        self.declare_parameter('rate_hz', 10.0)

        # brake levels
        self.declare_parameter('brake_low', -1.0)
        self.declare_parameter('brake_high', 1.0)

        # durations (seconds)
        self.declare_parameter('t_low_start', 5.0)   # first low hold
        self.declare_parameter('t_high_hold', 2.0)   # middle high hold
        self.declare_parameter('t_low_end', 5.0)     # final low hold

        # behavior
        self.declare_parameter('repeat', False)
        self.declare_parameter('stop_when_done', True)

        # constants for other fields
        self.declare_parameter('steering_constant', 0.0)
        self.declare_parameter('throttle_constant', -1.0)

        # -------- Read params --------
        topic = self.get_parameter('topic').value
        self.rate_hz = float(self.get_parameter('rate_hz').value)

        self.brake_low = float(self.get_parameter('brake_low').value)
        self.brake_high = float(self.get_parameter('brake_high').value)

        self.t_low_start = float(self.get_parameter('t_low_start').value)
        self.t_high_hold = float(self.get_parameter('t_high_hold').value)
        self.t_low_end = float(self.get_parameter('t_low_end').value)

        self.repeat = bool(self.get_parameter('repeat').value)
        self.stop_when_done = bool(self.get_parameter('stop_when_done').value)

        self.steering_const = float(self.get_parameter('steering_constant').value)
        self.throttle_const = float(self.get_parameter('throttle_constant').value)

        # -------- Segment boundaries --------
        # [0, A): low
        self.tA = self.t_low_start
        # [A, B): high
        self.tB = self.tA + self.t_high_hold
        # [B, C]: low
        self.tC = self.tB + self.t_low_end
        self.T_total = self.tC

        # -------- ROS I/O --------
        self.pub = self.create_publisher(String, topic, 3)
        self.t0 = self.get_clock().now()
        period = 1.0 / max(self.rate_hz, 1e-6)
        self.timer = self.create_timer(period, self._on_timer)

        self.get_logger().info(
            f'Publishing brake step to {topic} @ {self.rate_hz:.2f} Hz '
            f'(low {self.brake_low} for {self.t_low_start}s → high {self.brake_high} for {self.t_high_hold}s '
            f'→ low {self.brake_low} for {self.t_low_end}s) '
            f'{"[REPEAT]" if self.repeat else ""}'
        )

    # ---- pure profile ----
    def brake_of_t(self, t: float) -> float:
        """Return brake value at elapsed time t (seconds)."""
        if self.repeat and self.T_total > 0.0:
            t = t % self.T_total

        if t < self.tA:
            return self.brake_low
        if t < self.tB:
            return self.brake_high
        if t <= self.tC:
            return self.brake_low
        return self.brake_low  # after end (non-repeat)

    # ---- timer ----
    def _on_timer(self):
        t = (self.get_clock().now() - self.t0).nanoseconds * 1e-9
        brake = self.brake_of_t(t)

        msg = String()
        msg.data = (
            f'{{"control_input": {{"steering": {self.steering_const:.2f}, '
            f'"throttle": {self.throttle_const:.2f}, "brake": {brake:.2f}}}}}'
        )
        self.pub.publish(msg)

        if not self.repeat and self.stop_when_done and t > self.T_total:
            self.get_logger().info('Step sequence finished; stopping timer.')
            self.timer.cancel()

def main():
    rclpy.init()
    node = BrakeStepPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
