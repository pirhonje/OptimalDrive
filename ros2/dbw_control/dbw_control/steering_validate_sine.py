#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class SmoothWaveToWebsocket(Node):
    """
    Publishes JSON control to /to_websocket and /to_websocket_with_time.

    Motion profile (pure sine within active window):
      - idle_start seconds at y=0
      - active window of length T_active = t_up + t_down + t_return:
          tau ∈ [0, T_active] is mapped non-uniformly to θ ∈ [0, 2π]
          y(t) = sin(θ(tau))   # pure sine
          Segments (by time, not value):
            0→+1 in t_up seconds         (θ: 0 → π/2)
            +1→−1 in t_down seconds      (θ: π/2 → 3π/2)
            −1→0 in t_return seconds     (θ: 3π/2 → 2π)
      - idle_end seconds at y=0
      - if repeat is True, entire sequence loops.

    Scaling/clamping:
      steering = steering_amp * y
      (optional clamp_output keeps it in [-1, 1])
    """

    def __init__(self):
        super().__init__('smooth_wave_to_websocket')

        # Topics & timing
        self.declare_parameter('topic', '/to_websocket')
        self.declare_parameter('topic_with_time', '/to_websocket_with_time')
        self.declare_parameter('rate_hz', 20.0)

        # Idle durations (defaults per your spec)
        self.declare_parameter('idle_start', 3.0)
        self.declare_parameter('idle_end', 3.0)

        # Active segment durations (your asymmetric sine timing)
        self.declare_parameter('t_up', 1.0)       # 0 -> +1
        self.declare_parameter('t_down', 2.0)     # +1 -> -1
        self.declare_parameter('t_return', 1.0)   # -1 -> 0

        # Behavior
        self.declare_parameter('repeat', False)
        self.declare_parameter('clamp_output', True)

        # Output shaping
        self.declare_parameter('steering_amp', 1.0)  # keep 1.0 for [-1, 1]
        self.declare_parameter('throttle', -1.0)
        self.declare_parameter('brake_val', -1.0)

        # Read params
        topic = self.get_parameter('topic').value
        topic_with_time = self.get_parameter('topic_with_time').value
        self.rate_hz = float(self.get_parameter('rate_hz').value)

        self.idle_start = float(self.get_parameter('idle_start').value)
        self.idle_end = float(self.get_parameter('idle_end').value)

        self.t_up = float(self.get_parameter('t_up').value)
        self.t_down = float(self.get_parameter('t_down').value)
        self.t_return = float(self.get_parameter('t_return').value)
        self.T_active = self.t_up + self.t_down + self.t_return

        if self.T_active <= 0.0:
            raise ValueError("Active duration must be > 0 (t_up + t_down + t_return)")

        self.repeat = bool(self.get_parameter('repeat').value)
        self.clamp_output = bool(self.get_parameter('clamp_output').value)

        self.steering_amp = float(self.get_parameter('steering_amp').value)
        self.throttle_val = float(self.get_parameter('throttle').value)
        self.brake_val = float(self.get_parameter('brake_val').value)

        # Segment boundaries
        self.tA = self.idle_start                  # start of active window
        self.tD = self.tA + self.T_active          # end of active window
        self.T_total = self.tD + self.idle_end     # full sequence

        # Publishers
        self.pub = self.create_publisher(String, topic, 3)
        self.pub_with_time = self.create_publisher(String, topic_with_time, 3)

        # Timer
        self.t0 = self.get_clock().now()
        period = 1.0 / max(self.rate_hz, 1e-6)
        self.timer = self.create_timer(period, self._on_timer)

        # Log summary
        self.get_logger().info(
            f"Pure sine profile: idle_start={self.idle_start}s, "
            f"t_up={self.t_up}s, t_down={self.t_down}s, t_return={self.t_return}s, "
            f"idle_end={self.idle_end}s, repeat={self.repeat}, rate={self.rate_hz}Hz"
        )

    # ---------- Motion profile helpers ----------

    def _phase_mapping(self, tau: float) -> float:
        """
        Map local time tau ∈ [0, T_active] to phase θ ∈ [0, 2π] with piecewise
        *time* scaling (the waveform itself is a pure sine of θ).

        Segments:
          [0, t_up):      θ: 0 → π/2
          [t_up, t_up+t_down): θ: π/2 → 3π/2
          [t_up+t_down, T_active]: θ: 3π/2 → 2π
        """
        if tau < 0.0:
            return 0.0
        if tau < self.t_up:
            return (tau / self.t_up) * (math.pi / 2.0)
        if tau < self.t_up + self.t_down:
            return (math.pi / 2.0) + ((tau - self.t_up) / self.t_down) * math.pi
        # final quarter
        rem = tau - (self.t_up + self.t_down)
        return (3.0 * math.pi / 2.0) + (rem / self.t_return) * (math.pi / 2.0)

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _y_of_t(self, t: float) -> float:
        """Return waveform value per schedule."""
        # Loop if requested
        if self.repeat and self.T_total > 0.0:
            t = t % self.T_total

        # Idle before
        if t < self.tA:
            return 0.0

        # Active pure-sine window
        if t < self.tD:
            tau = t - self.tA
            theta = self._phase_mapping(tau)
            return math.sin(theta)

        # Idle after (or beyond total)
        return 0.0

    # ---------- Timer callback ----------

    def _on_timer(self):
        now = self.get_clock().now()
        t = (now - self.t0).nanoseconds * 1e-9

        y = self._y_of_t(t)
        steering = self.steering_amp * y
        if self.clamp_output:
            steering = self._clamp(steering, -1.0, 1.0)

        # Publish base JSON
        msg = String()
        msg.data = (
            f'{{"control_input":{{"steering":{steering:.4f},'
            f'"throttle":{self.throttle_val:.2f},"brake":{self.brake_val}}}}}'
        )
        self.pub.publish(msg)

        # Publish with time
        stamp = now.to_msg()
        msg2 = String()
        msg2.data = (
            f'{{"control_input":{{"steering":{steering:.4f},'
            f'"throttle":{self.throttle_val:.2f},"brake":{self.brake_val}}},'
            f'"ros_time":{{"sec":{stamp.sec},"nanosec":{stamp.nanosec}}}}}'
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
