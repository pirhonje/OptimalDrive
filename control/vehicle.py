import json
import copy
import can
import ruamel.yaml
import time

yaml = ruamel.yaml.YAML()
yaml.preserve_quotes = True

class Vehicle:
    def __init__(self):
        # Actual values from CAN Bus, if implemented
        self.throttle_actl = None
        self.brake_actl = None
        self.steering_actl = None

        # Actuator states, updated by Canbus_handler
        self.throttle_pos = 0.0
        self.throttle_nmt_state = "None"
        self.throttle_motion_state = "None"
        self.throttle_timestamp = 0

        self.brake_pos = 0.0
        self.brake_nmt_state = "None"
        self.brake_motion_state = "None"
        self.brake_timestamp = 0

        self.steering_pos = 0
        self.steering_nmt_state = "None"
        self.steering_motion_state = "None"
        self.steering_timestamp = 0
        self.steering_preop_timestamp = 0
        self.steering_raw_state = None
        self.steering_zero_offset = 0

        # These shouldn't be directly accessed. Use Vehicle.get_control_request() and Vehicle.set_control_request()
        self._throttle_request = 0.0
        self._throttle_request_timestamp = 0
        self._brake_request = 0.0
        self._brake_request_timestamp = 0
        self._steering_request = 0
        self._steering_request_timestamp = 0

        self._throttle_min_flag = False
        self._brake_min_flag = False

        self.control_mode = 'Normal' # Normal or Config

        # "Static" variables
        self.config = None
        self.config_name = None
        self.filename = None

        self.throttle_min: int = None
        self.throttle_max: int = None

        self.brake_min: int = None
        self.brake_max: int = None

        self.steering_min: int = None
        self.steering_max: int = None
        self.steering_v_max: int = None
        self.steering_a_max: int = None
        self.steering_n: int = None

        self.can_interface = None
        self.can_channel = None
        self.can_bitrate = None

        self.can_throttle_id = None
        self.can_brake_id = None
        self.can_steering_id = None

        self.can_throttle_node = None
        self.can_brake_node = None
        self.can_steering_node = None
        self.can_heartbeat = None

        # Map controller axis (-1 to 1) to the configured actuator range
        self.throttle_scaler = None
        self.brake_scaler = None
        self.steering_scaler = None

        # Seconds. Vehicle.get_control_request() will not serve request older than this
        # and sets the request variables to the resting position.
        # Prevents e.g. throttle getting "stuck" down in case of client getting disconnected etc.
        self._request_timeout = 1

    def load_config(self, filename):
        with open(filename, "r") as f:
            try:
                config = yaml.load(f)
                #print(config)
                self.config_name = config["name"]
                self.throttle_min = config["limits"]["throttle_min"]
                self.throttle_max = config["limits"]["throttle_max"]
                self.brake_min = config["limits"]["brake_min"]
                self.brake_max = config["limits"]["brake_max"]
                self.steering_min = config["limits"]["steering_min"]
                self.steering_max = config["limits"]["steering_max"]
                self.steering_v_max = config["limits"]["steering_v_max"]
                self.steering_a_max = config["limits"]["steering_a_max"]
                self.steering_n = config["limits"]["steering_n"]
                self._steering_request =  self.steering_min
                self._brake_request = self.brake_min
                self._throttle_request = self.throttle_min

                self.can_interface = config["can"]["interface"]
                self.can_channel = config["can"]["channel"]
                self.can_bitrate = config["can"]["bitrate"]
                self.can_throttle_id = config["can"]["throttle_id"]
                self.can_brake_id = config["can"]["brake_id"]
                self.can_steering_id = config["can"]["steering_id"]

                self.throttle_scaler = make_interpolator(-1, 1, self.throttle_min, self.throttle_max)
                self.brake_scaler = make_interpolator(-1, 1, self.brake_min, self.brake_max)
                self.steering_scaler = make_interpolator(-1, 1, self.steering_min, self.steering_max)

                self.config = config
                self.filename = filename

            except Exception as exc:
                print(exc)

    def update_config(self, key, value):
        filename = self.filename
        config = None
        with open(filename) as f:
            try:
                config = yaml.load(f)
                print(config)
                config['limits'][key] = value
            except Exception as exc:
                print(f'{filename} {exc}')
        with open(filename, 'r+') as f:
            yaml.dump(config, f)



    def config_as_JSON(self):
        # TODO: The config object is based on the text file, and does not get updated when new limits are set. This is a workaround

        config = copy.deepcopy(self.config)

        config["limits"]["throttle_min"] = self.throttle_min
        config["limits"]["throttle_max"] = self.throttle_max
        config["limits"]["brake_min"] = self.brake_min
        config["limits"]["brake_max"] = self.brake_max
        config["limits"]["steering_min"] = self.steering_min
        config["limits"]["steering_max"] = self.steering_max

        return json.dumps({'config': config, 'control_mode': self.control_mode})


    def as_JSON(self):
        vehicle_state = {
            "throttle": self.throttle_actl,
            "brake": self.brake_actl,
            "steering": self.steering_actl
        }
        actuator_state = {
            "throttle": {
                "pos": self.throttle_pos,
                "request": self._throttle_request,
                "nmt_state": self.throttle_nmt_state,
                "motion_state": self.throttle_motion_state},
            "brake": {
                "pos": self.brake_pos,
                "request": self._brake_request,
                "nmt_state": self.brake_nmt_state,
                "motion_state": self.brake_motion_state},
            "steering": {
                "pos": self.steering_pos - self.steering_zero_offset,
                "request": self._steering_request,
                "nmt_state": self.steering_nmt_state,
                "motion_state": self.steering_motion_state},
        }
        return json.dumps({"vehicle_state": vehicle_state, "actuator_state": actuator_state, 'control_mode': self.control_mode})


    def set_control_request(self, actuator, position):
        if self.control_mode == 'Normal':
            try: # In case input can't be cast to float
                now = time.time()
                position = float(position)
                if actuator == 'throttle':
                    scaled_pos = self.throttle_scaler(position)
                    self._throttle_request = scaled_pos
                    self._throttle_request_timestamp = now
                    # anti backslash
                    if self.throttle_pos - 0.5 <= self.throttle_min <= self.throttle_pos + 0.5 and scaled_pos == self.throttle_min:
                        self._throttle_min_flag = True 
                    if scaled_pos > self.throttle_min:
                        self._throttle_min_flag = False
                if actuator == 'brake':
                    scaled_pos = self.brake_scaler(position)
                    self._brake_request = self.brake_scaler(position)
                    self._brake_request_timestamp = now
                    if self.brake_pos - 0.5 <= self.brake_min <= self.brake_pos + 0.5 and scaled_pos == self.brake_min:
                        self._brake_min_flag = True 
                    if scaled_pos > self.brake_min:
                        self._brake_min_flag = False
                if actuator == 'steering':
                    self._steering_request = self.steering_scaler(position)
                    self._steering_request_timestamp = now
            except Exception as exc:
                print(exc)
        elif self.control_mode == 'Config':
            try: # In case input can't be cast to float
                now = time.time()
                position = float(position)
                if actuator == 'throttle':
                    self._throttle_request = clamp(position, 0, 100)
                    self._throttle_request_timestamp = now
                if actuator == 'brake':
                    self._brake_request = clamp(position, 0, 100)
                    self._brake_request_timestamp = now
                if actuator == 'steering':
                    self._steering_request = position
                    self._steering_request_timestamp = now
            except Exception as exc:
                print(exc)

    def get_control_request(self):
        now = time.time()

        if self.control_mode == 'Normal':
            # If no new inputs have been received after request_timeout, home actuator. Disabled in Config mode
            if now - self._throttle_request_timestamp > self._request_timeout:
                self._throttle_request = self.throttle_min

            if now - self._brake_request_timestamp > self._request_timeout:
                self._brake_request = self.brake_min

            if now - self._steering_request_timestamp > self._request_timeout:
                self._steering_request = 0 


            if self._throttle_min_flag:
                self._throttle_request = float(self.throttle_min)+1

            if self._brake_min_flag:
                self._brake_request = float(self.brake_min)+1

        return self._throttle_request, self._brake_request, self._steering_request

    def set_new_limit(self, actuator, limit_type, value):
        try: # In case input can't be cast to int
            value = int(value)
            if actuator == 'throttle':
                if limit_type == 'max':
                    self.throttle_max = value
                    self.update_config('throttle_max', value)
                elif limit_type == 'min':
                    self.throttle_min = value
                    self.update_config('throttle_min', value)
                self.throttle_scaler = make_interpolator(-1, 1, self.throttle_min, self.throttle_max)
            if actuator == 'brake':
                if limit_type == 'max':
                    self.brake_max = value
                    self.update_config('brake_max', value)
                elif limit_type == 'min':
                    self.brake_min = value
                    self.update_config('brake_min', value)
                self.brake_scaler = make_interpolator(-1, 1, self.brake_min, self.brake_max)
            if actuator == 'steering':
                if limit_type == 'max':
                    self.steering_max = value
                    self.update_config('steering_max', value)
                elif limit_type == 'min':
                    self.steering_min = value
                    self.update_config('steering_min', value)
                self.steering_scaler = make_interpolator(-1, 1, self.steering_min, self.steering_max)
        except Exception as exc:
                print(exc)


    def check_timestamps(self):
        now = time.time()
        if (now - self.throttle_timestamp) > self._request_timeout:
            self.throttle_nmt_state = "Connection lost"
        if (now - self.brake_timestamp) > self._request_timeout:
            self.brake_nmt_state = "Connection lost"
        if (now - self.steering_timestamp) > self._request_timeout:
            self.steeting_nmt_state = "Connection lost"


def clamp(n, minn, maxn):
    return min(max(n, minn), maxn)

def make_interpolator(in_min, in_max, out_min, out_max):
    # Figure out how 'wide' each range is
    in_span = in_max - in_min
    out_span = out_max - out_min

    # Compute the scale factor between left and right values
    scale_factor = float(out_span) / float(in_span)

    # create interpolation function using pre-calculated scale_factor
    def interp_fn(value):
        return float(out_min + (value - in_min)*scale_factor)

    return interp_fn
