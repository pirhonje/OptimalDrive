import time
import canopen
import functools

# Linak Run Commands
# 0-64255       Run to position
# 64256         Clear ErrorCode register (see 0x1001)
# 64257         Command run actuator out
# 64258         Command run actuator in
# 64259         Command stop actuator
# 64260         Command run actuator out (Recovery mode)
# 64261         Command run actuator in (Recovery mode)
# 64262-65535   Invalid value, actuator will not run

def init(v):
    cb = canopen.Network()
    cb.connect(channel=v.can_channel, interface=v.can_interface)
    cb.check() # Check that no fatal error has occurred in the receiving thread.

    # Start producer heartbeat every 100 ms
    cb_heartbeat = cb.send_periodic(0x701, b'\x05', 0.100)

    # Add LINAKs
    la_throttle = cb.add_node(v.can_throttle_id, 'linak.eds')
    la_brake = cb.add_node(v.can_brake_id, 'linak.eds')
    la_throttle.rpdo.read()
    la_brake.rpdo.read()
    la_throttle.tpdo.read()
    la_brake.tpdo.read()

    # Add Servo
    dsy_steer = cb.add_node(v.can_steering_id, 'DSY-C.eds')
    dsy_steer.rpdo.read()
    dsy_steer.tpdo.read()

    # Reset network
    la_throttle.nmt.state = 'RESET'
    la_brake.nmt.state = 'RESET'
    dsy_steer.nmt.state = 'RESET'
    time.sleep(2)

    # Set heartbeat time for Linaks as per datasheet.
    la_throttle.sdo['Consumer Heartbeat Time.Consumer Heartbeat Time'].raw = 0x0100C8
    time.sleep(0.5)
    la_brake.sdo['Consumer Heartbeat Time.Consumer Heartbeat Time'].raw = 0x0100C8
    time.sleep(0.5)

    # Set linak to send a hearbeat every 250ms
    la_throttle.sdo["Producer Heartbeat Time"].raw = 250
    time.sleep(0.5)
    la_brake.sdo["Producer Heartbeat Time"].raw = 250
    time.sleep(0.5)
    # And report received response
    bound_linak_hb_throttle = functools.partial(linak_report_nmt, id=v.can_throttle_id, v=v)
    bound_linak_hb_brake = functools.partial(linak_report_nmt, id=v.can_brake_id, v=v)
    la_throttle.nmt.add_heartbeat_callback(bound_linak_hb_throttle)
    la_brake.nmt.add_heartbeat_callback(bound_linak_hb_brake)

    # Monitor linak states and report response. tpdo1 isn't explicitly configured here as the built-in default config is OK
    bound_linak_reporter = functools.partial(linak_report_status, v=v)
    la_throttle.tpdo[1].add_callback(bound_linak_reporter)
    la_brake.tpdo[1].add_callback(bound_linak_reporter)

    # Set servo to send a hearbeat every 250ms
    dsy_steer.sdo["Producer Heartbeat Time"].raw = 250
    dsy_steer.sdo['Gear ratio.Motor revolutions'].raw = 1
    dsy_steer.sdo['Gear ratio.Shaft revolutions'].raw = 1
    # And report received response
    bound_dsy_hb = functools.partial(dsy_report_nmt, v=v)
    dsy_steer.nmt.add_heartbeat_callback(bound_dsy_hb)

    # Configure servo to receive control and position commands
    dsy_steer.rpdo[1].clear()
    dsy_steer.rpdo[1].add_variable('Controlword')
    dsy_steer.rpdo[1].add_variable('Target position')
    dsy_steer.rpdo[1].enabled = True
    dsy_steer.rpdo[1].save()
    dsy_steer.rpdo[1].transmit()
    time.sleep(0.2)

    # Configure servo to send CiA 401 status
    dsy_steer.tpdo[1].clear()
    dsy_steer.tpdo[1].add_variable('Statusword')
    dsy_steer.tpdo[1].add_variable('Position actual value')
    dsy_steer.tpdo[1].trans_type = 254
    dsy_steer.tpdo[1].event_time = 250
    dsy_steer.tpdo[1].enabled = True
    dsy_steer.tpdo[1].save()
    time.sleep(0.2)
    # And report received response
    bound_dsy_reporter = functools.partial(dsy_report_status, v=v)
    dsy_steer.tpdo[1].add_callback(bound_dsy_reporter)

    # Start nodes
    la_throttle.nmt.state = 'OPERATIONAL'
    la_brake.nmt.state = 'OPERATIONAL'
    dsy_steer.nmt.state = 'OPERATIONAL'

    # Init linaks and set to stopped state
    linak_init_stop(la_throttle)
    time.sleep(0.5)
    linak_init_stop(la_brake)
    time.sleep(0.5)

    # Init servo drive to profile position mode
    dsy_init_pp(dsy_steer)

    dsy_steer.sdo["Controlword"].raw = 0x06 # No Fault -> Servo Ready
    time.sleep(0.5)
    dsy_steer.sdo["Controlword"].raw = 0x07 # Servo Ready -> Waiting to enable
    time.sleep(0.5)
    dsy_steer.sdo["Controlword"].raw = 0x0F # Waiting to enable -> Running
    time.sleep(0.5)

    linak_clear_errors(la_throttle)
    time.sleep(0.5)
    linak_clear_errors(la_brake)
    time.sleep(0.5)

    return cb_heartbeat, la_throttle, la_brake, dsy_steer

def linak_report_status(message, v):
    node_id = message.cob_id & 0x7F # Extract node-id from cob-id
    if node_id == v.can_throttle_id:
        v.throttle_pos = message["Actuator Status.Position"].raw * 0.1
        v.throttle_motion_state = linak_decode_error(message["Actuator Status.Error Code"].raw)
    elif node_id == v.can_brake_id:
        #v.brake_timestamp = message.timestamp
        v.brake_pos = message["Actuator Status.Position"].raw * 0.1
        v.brake_motion_state = linak_decode_error(message["Actuator Status.Error Code"].raw)

def linak_decode_error(s: int):
    errors = ["No error", 'Need Stop Command', 'Hall error', 'Overvoltage', 'Undervoltage', 'Failed to maintain heartbeat', 
        'Endstop reached error', 'Temperature error', 'Heartbeat error (internal)', 'SMPS error (internal)', 
        'Current measurement (internal)']
    if 0 <= s <= 10:
        return errors[s]
    elif s == 254:
        return 'Internal fault (not specified)'
    elif s == 255:
        return 'External fault (not specified)]'
    return 'Unknown error'

def linak_report_nmt(message, id, v):
    nmt_state = decode_nmt(message)
    if id == v.can_throttle_id:
        v.throttle_timestamp = time.time()
        if v.throttle_nmt_state != nmt_state:
            v.throttle_nmt_state = nmt_state
            print("Throttle ", nmt_state)
    elif id == v.can_brake_id:
        v.brake_timestamp = time.time()
        if v.brake_nmt_state != nmt_state:
            v.brake_nmt_state = nmt_state
            print("Brake ", nmt_state)

def linak_init_stop(node):
    node.rpdo[1]['Actuator Command.Position'].raw = 64259 # Stop Actuator
    node.rpdo[1]['Actuator Command.Current'].raw = 251 # Default
    node.rpdo[1]['Actuator Command.Speed'].raw = 251 # Default
    node.rpdo[1]['Actuator Command.Soft Start'].raw = 1#1 # No soft start
    node.rpdo[1]['Actuator Command.Soft Stop'].raw = 1#1 # No soft stop
    node.rpdo[1].transmit()

def linak_clear_errors(node):
    node.rpdo[1]['Actuator Command.Position'].raw = 64256 # Clear ErrorCode register
    node.rpdo[1].transmit()
    print("Sent clear")

def linak_run_to(node, mm: float):
    val = mm * 10 # 0.1mm per bit
    print(val)
    assert 0 <= val <= 64255, "Linak position out of range"
    node.rpdo[1]['Actuator Command.Position'].raw = val
    node.rpdo[1].transmit()

def linak_stop(node):
    node.rpdo[1]['Actuator Command.Position'].raw = 64259 # Stop Actuator
    node.rpdo[1].transmit()
    print("Sent stop")


def dsy_init_pp(node):
    node.sdo['Modes of operation'].raw = 1 # Profile Position
    node.sdo['Profile velocity'].raw = 30 # motor rev per sec
    node.sdo['Profile acceleration'].raw = 40
    node.sdo['Profile deceleration'].raw = 40
    time.sleep(0.02)
    node.sdo['Pos fac.Numerator'].raw = 364.1*20#(360*20) #131072#4000
    node.sdo['Pos fac.Feed constant'].raw = 1
    time.sleep(0.02)
    node.sdo['Polarity'].raw = 1

def dsy_run_to(node, d):
    
    ticks = int(round(d))
    node.rpdo[1]['Controlword'].raw = 0x2F
    node.rpdo[1]['Target position'].raw = d
    node.rpdo[1].transmit()
    node.rpdo[1]['Controlword'].raw = 0x3F
    #node.rpdo[1]['Target position'].raw = d
    node.rpdo[1].transmit()

    
def dsy_report_nmt(message, v):
    new_state = decode_nmt(message)
    now = time.time()

    if v.steering_nmt_state != "Pre-operational" and new_state == "Pre-operational":
        v.steering_preop_timestamp = now # Set timestamp only when DSY *enters* Preop
    
    if v.steering_nmt_state == "Pre-operational" and (now - v.steering_preop_timestamp > 0.2):
        v.can_steering_node.nmt.state = 'OPERATIONAL'

    v.steering_nmt_state = new_state


def dsy_report_status(message, v):
    new_state = dsy_decode_status(message['Statusword'].raw)
    #new_raw_state = message['Statusword'].raw
    v.steering_timestamp = message.timestamp
    if new_state != v.steering_motion_state:
        #print(f'DSY: {new_state} {new_raw_state:>16b}')
        print(f'DSY: {new_state}')
    v.steering_motion_state = new_state
    if message['Position actual value'].raw > -16777216: # Sometimes DSY overflows for a single update
        v.steering_pos = message['Position actual value'].raw 

def dsy_decode_status(s):
    m1 = 0b0000000001001111  # For init, no fault, fault stop, fault
    m2 = 0b0000000001101111  # For ready, waiting enable, running, quick stop

    if ((s & m1) == 0):
        print("init, J")
        return "Initialization"
    elif ((s & m1) == 64):
        print("servo no fault, J")
        return "Servo No Fault"
    elif ((s & m1) == 15):
        print("fault stop, J")
        return "Fault Stop"
    elif ((s & m1) == 8):
        print("fault, J")
        return "Fault"
    elif ((s & m2) == 33):
        print("servo ready, J")
        return "Servo Ready"
    elif ((s & m2) == 35):
        print("waiting, J")
        return "Waiting to Enable"
    elif ((s & m2) == 39):
        #print("running, J")
        return "Servo Running"
    elif ((s & m2) == 7):
        print("quick stop, J")
        return "Quick Stop"

    return "Unknown State"

def dsy_decode_status_p(s):
    m1 = 0b0000000001001111  # For init, no fault, fault stop, fault
    m2 = 0b0000000001101111  # For ready, waiting enable, running, quick stop

    if (s & m1 == 0):
        return "Initialization"
    elif (s & m1 == 64):
        return "Servo No Fault"
    elif (s & m1 == 15):
        return "Fault Stop"
    elif (s & m1 == 8):
        return "Fault"
    elif (s & m2 == 33):
        return "Servo Ready"
    elif (s & m2 == 35):
        return "Waiting to Enable"
    elif (s & m2 == 39):
        return "Servo Running"
    elif (s & m2 == 7):
        return "Quick Stop"

    return "Unknown State"

def decode_nmt(s):
    if (s == 0x00):
        print("bootup, Je")
        return "Bootup"
    elif (s == 0x04):
        print("stopped, Je")
        return "Stopped"
    elif (s == 0x05):
        #print("operational, Je")
        return "Operational"
    elif (s == 0x7F):
        print("pre-operational, Je")
        return "Pre-operational"

def dsy_state_machine(v):
    if v.steering_motion_state == "Servo No Fault":
        v.can_steering_node.rpdo[1].clear()
        v.can_steering_node.rpdo[1].add_variable('Controlword')
        v.can_steering_node.rpdo[1].add_variable('Target position')
        v.can_steering_node.rpdo[1].enabled = True
        v.can_steering_node.rpdo[1].save()
        v.can_steering_node.rpdo[1].transmit()
        dsy_init_pp(v.can_steering_node)
        v.can_steering_node.sdo["Controlword"].raw = 0x06
        print("No Fault -> Servo Ready")
    elif v.steering_motion_state == "Servo Ready":
        v.can_steering_node.sdo["Controlword"].raw = 0x07
        print("Servo Ready -> Waiting to Enable")
    elif v.steering_motion_state == "Waiting to Enable":
        v.can_steering_node.sdo["Controlword"].raw = 0x0F
        print("Waiting to Enable -> Servo Running")
    elif v.steering_motion_state == "Fault":
        v.can_steering_node.sdo["Controlword"].raw = 0x06
        print("Detected fault, sent 0x06")


def dsy_set_new_zero(v):
    v.steering_zero_offset = v.steering_pos


