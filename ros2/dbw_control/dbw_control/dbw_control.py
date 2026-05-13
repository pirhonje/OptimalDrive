import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32, Bool, String
from collections import deque

class PoseSubscriber(Node):
    def __init__(self):
        super().__init__('pose_subscriber')
        self.hand_up = False
        self.steering = 0.0
        self.brake = 1
        self.throttle = -1

        # P+filter params
        self.Kp = 0.003          # tune
        self.deadband = 3        # pixels, tune
        self.err_buf = deque(maxlen=5)

        self.create_subscription(Int32, '/pose_detection/dist_to_center', self.dist_cb, 3)
        self.create_subscription(Bool, '/pose_detection/hand_up', self.hand_cb, 3)

        self.ctrl_pub = self.create_publisher(String, '/to_websocket', 3)

    def publish_control(self):
        msg = String()
        msg.data = (
            f'{{"control_input": {{"steering": {self.steering:.2f}, '
            f'"throttle": {self.throttle:.2f}, "brake": {self.brake}}}}}'
        )
        self.ctrl_pub.publish(msg)

    def dist_cb(self, msg: Int32):
        if not self.hand_up:
            self.steering = 0.0
            self.publish_control()
            return

        # Low-pass: moving average of last 5 errors
        self.err_buf.append(float(msg.data))
        avg_err = sum(self.err_buf) / len(self.err_buf)

        # Deadband
        if abs(avg_err) < self.deadband:
            control = 0.0
        else:
            control = self.Kp * avg_err

        # Clamp (same range you used)
        control = max(-0.5, min(0.5, control))
        self.steering = control
        self.publish_control()

    def hand_cb(self, msg: Bool):
        self.hand_up = msg.data
        self.brake = -0.2 if self.hand_up else 1
        self.publish_control()

def main(args=None):
    rclpy.init(args=args)
    node = PoseSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
