import asyncio
import os
import time


import websocket_server as ws
import canbus_handler as cb
from vehicle import Vehicle

CAN_DISABLE = os.environ.get('DEVELOPMENT', 'false').lower() == 'true'

def main():
    v = Vehicle()
    v.load_config("config.yml")
    #print(f'Steering: {v.steering_min}..{v.steering_max}, Throttle: {v.throttle_min}..{v.throttle_max}, Brake: {v.brake_min}..{v.brake_max}')

    # The server runs on its own thread and continuously updates the vehicle object with the received requests
    ws.start_thread(v)

    if not CAN_DISABLE:
        v.can_heartbeat, v.can_throttle_node, v.can_brake_node, v.can_steering_node = cb.init(v)

    control_loop(v)

def control_loop(v):
    while True:
        v.check_timestamps() # Check if the actuators are respongind to NMT messages
        throttle, brake, steering = v.get_control_request()
        if not CAN_DISABLE:
            try:
                cb.dsy_state_machine(v)
                cb.linak_run_to(v.can_throttle_node, throttle)
                cb.linak_run_to(v.can_brake_node, brake)
                cb.dsy_run_to(v.can_steering_node, steering + v.steering_zero_offset)
            except Exception as exc:
                print(exc)
        time.sleep(0.05)


async def send_control_requests(v):
    throttle_request, brake_request, steering_request = v.get_control_request()



if __name__ == "__main__":
    main()