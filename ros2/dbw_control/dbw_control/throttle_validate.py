#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from time import monotonic


class ThrottleStepPublisher(Node):
    """
    Publishes JSON:
      {"control_input": {"steering": <const>, "throttle": <value>, "brake": <const>}}

    Profile:
      0 for 5s → 0.5 for 2s → 1.0 for 2s → 0.5 for 2s → 0 for 5s
    """

    def __init__(self):
        super().__init__('throttle_step_publisher')

        # -------- Parameters --------
        self.declare_parameter('topic', '/to_websocket')
        self.declare_parameter('rate_hz', 20.0)

        # durations (seconds)
        self.declare_parameter('t0_start_hold', 5.0)  # initial 0
        self.declare_parameter('t05a_hold', 2.0)      # first 0.5
        self.declare_parameter('t1_hold', 2.0)        # 1.0
        self.declare_parameter('t05b_hold', 2.0)      # second 0.5
        self.declare_parameter('t0_end_hold', 5.0)    # final 0

        # behavior
        self.declare_parameter('repeat', False)
        self.declare_parameter('stop_when_done', True)

        # constants for other fields
        self.declare_parameter('steering_constant', 0.0)
        self.declare_parameter('brake_constant', -1.0)

        # -------- Read params --------
        topic = self.get_parameter('topic').value
        self.rate_hz = float(self.get_parameter('rate_hz').value)

        self.t0_start_hold = float(self.get_parameter('t0_start_hold').value)
        self.t05a_hold = float(self.get_parameter('t05a_hold').value)
        self.t1_hold = float(self.get_parameter('t1_hold').value)
        self.t05b_hold = float(self.get_parameter('t05b_hold').value)
        self.t0_end_hold = float(self.get_parameter('t0_end_hold').value)

        self.repeat = bool(self.get_parameter('repeat').value)
        self.stop_when_done = bool(self.get_parameter('stop_when_done').value)

        self.steering_const = float(self.get_parameter('steering_constant').value)
        self.brake_const = float(self.get_parameter('brake_constant').value)

        # -------- Segment boundaries (cumulative) --------
        self.tA = self.t0_start_hold
        self.tB = self.tA + self.t05a_hold
        self.tC = self.tB + self.t1_hold
        self.tD = self.tC + self.t05b_hold
        self.tE = self.tD + self.t0_end_hold
        self.T_total = self.tE

        # -------- ROS I/O --------
        self.pub = self.create_publisher(String, topic, 3)

        # Use steady wall clock for elapsed time (robust to ROS/sim time jumps)
        self.t0 = monotonic()

        period = 1.0 / max(self.rate_hz, 1e-6)
        self.timer = self.create_timer(period, self._on_timer)

        self.get_logger().info(
            f'Publishing throttle steps to {topic} @ {self.rate_hz:.2f} Hz: '
            f'0 for {self.t0_start_hold}s → 0.5 for {self.t05a_hold}s → 1.0 for {self.t1_hold}s '
            f'→ 0.5 for {self.t05b_hold}s → 0 for {self.t0_end_hold}s '
            f'{"[REPEAT]" if self.repeat else ""}'
        )

    # ---- profile ----
    def throttle_of_t(self, t: float) -> float:
        if self.repeat and self.T_total > 0:
            t = t % self.T_total

        if t < self.tA:      # 0
            return -1.0
        if t < self.tB:      # 0.5
            return 0
        if t < self.tC:      # 1.0
            return 1.0
        if t < self.tD:      # 0.5
            return 0
        if t <= self.tE:     # 0
            return -1
        return -1.0

    # ---- timer ----
    def _on_timer(self):
        t = monotonic() - self.t0
        throttle = self.throttle_of_t(t)

        msg = String()
        msg.data = (
            f'{{"control_input": {{"steering": {self.steering_const:.2f}, '
            f'"throttle": {throttle:.2f}, "brake": {self.brake_const:.2f}}}}}'
        )
        self.pub.publish(msg)

        if not self.repeat and self.stop_when_done and t > self.T_total:
            self.get_logger().info('Step sequence finished; stopping timer.')
            self.timer.cancel()


def main():
    rclpy.init()
    node = ThrottleStepPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
