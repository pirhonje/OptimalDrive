import asyncio
import json
import websockets
import functools
import canbus_handler as cb
from threading import Thread
from websockets.exceptions import ConnectionClosed

# Holds list of connected websocket clients
clients = set()

async def handler(websocket, v):
    clients.add(websocket)
    try:
        await asyncio.gather(
            rx_handler(websocket, v),
            tx_handler(websocket, v),
        )
    finally:
        # Unregister disconnected user
        clients.remove(websocket)
        websockets.broadcast(clients, users_event())

async def send_config(websocket, v):
    try:
        await websocket.send(v.config_as_JSON())
    except ConnectionClosed:
        print('ConnectionClosed')


async def rx_handler(websocket, v):
    async for message in websocket:
        #print(message)
        event = json.loads(message)

        if 'config' in event:
            print("Client requested config")
            if event['config'] == 'request':
                await send_config(websocket, v)
        if 'control_request' in event:
            print(event)
            try:
                actuator = event['control_request']['actuator']
                position = event['control_request']['position']
                v.set_control_request(actuator, position)
            except Exception as exc:
                print(exc)
        if 'mode_change' in event:
            print(event)
            if event['mode_change'] == 'Normal':
                v.control_mode = 'Normal'
            elif event['mode_change'] == 'Config':
                v.control_mode = 'Config'
        if 'control_input' in event:
            try: 
                v.set_control_request('brake', event['control_input']['brake'])
                v.set_control_request('throttle', event['control_input']['throttle'])
                v.set_control_request('steering', event['control_input']['steering'])
            except Exception as exc:
                print(exc)
        if 'command' in event:
            print(event)
            if event['command']['actuator'] == 'throttle':
                match event['command']['command']:
                    case 'stop':
                        cb.linak_stop(v.can_throttle_node)
                    case 'clear':
                        cb.linak_clear_errors(v.can_throttle_node)
                    case 'set-max':
                        v.set_new_limit('throttle', 'max', event['command']['value'])
                        await send_config(websocket, v)
                    case 'set-min':
                        v.set_new_limit('throttle', 'min', event['command']['value'])
                        await send_config(websocket, v)
            elif event['command']['actuator'] == 'brake':
                match event['command']['command']:
                    case 'stop':
                        cb.linak_stop(v.can_brake_node)
                    case 'clear':
                        cb.linak_clear_errors(v.can_brake_node)
                    case 'set-max':
                        v.set_new_limit('brake', 'max', event['command']['value'])
                        await send_config(websocket, v)
                    case 'set-min':
                        v.set_new_limit('brake', 'min', event['command']['value'])
                        await send_config(websocket, v)
            elif event['command']['actuator'] == 'steering':
                match event['command']['command']:
                    case 'stop':
                        cb.linak_stop(v.can_steering_node)
                    case 'clear':
                        cb.linak_clear_errors(v.can_steering_node)
                    case 'set-max':
                        v.set_new_limit('steering', 'max', event['command']['value'])
                        await send_config(websocket, v)
                    case 'set-min':
                        v.set_new_limit('steering', 'min', event['command']['value'])
                        await send_config(websocket, v)
                    case 'set-zero':
                        cb.dsy_set_new_zero(v)
                        print("New Zero Set")

        #if 'control_input' in event:
        #    if 'throttle' in event['control_input']:
        #        v.set_control_request(throttle=event['control_input']['throttle'])
        #    if 'brake' in event['control_input']:
        #        v.set_control_request(brake=event['control_input']['brake'])
        #    if 'steering' in event['control_input']:
        #        v.set_control_request(steering=event['control_input']['steering'])


async def tx_handler(websocket, v):
    while True:
        try:
            message = v.as_JSON()
            await websocket.send(message)
            await asyncio.sleep(0.05)
        except ConnectionClosed:
            break

# Runs when a client (dis)connects
def users_event():
    return json.dumps({"clients": len(clients)})
    print("(dis)connected")


def start_thread(vehicle):
    ws_run = Thread(target=asyncio.run, args=(ws_bootstrap(vehicle),), daemon=True)
    ws_run.start()


async def ws_bootstrap(vehicle):
    bound_handler = functools.partial(handler, v=vehicle) # https://websockets.readthedocs.io/en/stable/faq/server.html#how-do-i-pass-arguments-to-the-connection-handler

    async with websockets.serve(bound_handler, "0.0.0.0", 8888):
        print("Websocket server running")
        await asyncio.Future()  # run forever
