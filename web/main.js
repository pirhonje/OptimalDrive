var ws;
var ws_address;
var timeout = 250;

var steering_axis;
var throttle_axis;
var brake_axis;
var steering_gamma;
var throttle_gamma;
var brake_gamma;

window.addEventListener("DOMContentLoaded", () => {
  // Set controller axis and gamma if saved
  steering_axis = localStorage.getItem('steering_axis');
  throttle_axis = localStorage.getItem('throttle_axis');
  brake_axis = localStorage.getItem('brake_axis');

  if (localStorage.getItem('steering_gamma') === null) {
    localStorage.setItem('steering_gamma', 2.0);
  }
  steering_gamma = localStorage.getItem('steering_gamma')
  document.getElementById('steering-gamma').value = steering_gamma;
  document.getElementById("steering-gamma-val").innerHTML = steering_gamma;

  if (localStorage.getItem('throttle_gamma') === null) {
    localStorage.setItem('throttle_gamma', 2.0);
  }
  throttle_gamma = localStorage.getItem('throttle_gamma')
  document.getElementById('throttle-gamma').value = throttle_gamma;
  document.getElementById("throttle-gamma-val").innerHTML = throttle_gamma;

  if (localStorage.getItem('brake_gamma') === null) {
    localStorage.setItem('brake_gamma', 2.0);
  }
  brake_gamma = localStorage.getItem('brake_gamma')
  document.getElementById('brake-gamma').value = brake_gamma;
  document.getElementById("brake-gamma-val").innerHTML = brake_gamma;

  // Set WS address
  if (localStorage.getItem('ws_address') === null) {
    if (window.location.protocol != 'http:') {
      ws_address = '127.0.0.1:8888'
    } else {
      ws_address = window.location.hostname + ":8888";
    }
    address_modal();
  } else {
    ws_address = localStorage.getItem('ws_address');
  }
  connect();

  init();
});

function address_modal() {
  input = window.prompt("Websocket address:", ws_address);
  if (input !== null & input != "") {
    ws_address = input
    localStorage.setItem('ws_address', ws_address);
  }
};

function connect() {
  ws = new WebSocket('ws://' + ws_address);
  ws.onopen = function() {
    timeout = 250;
    document.getElementById("ip").innerHTML = 'Connected to: ' + ws_address;
    ws.send(JSON.stringify({'config': 'request'}))
  };

  ws.onmessage = function(e) {
    //console.log('Message:', e.data);
    message_handler(e.data);
  };

  ws.onclose = function(e) {
    timeout = Math.min(5000, timeout+=timeout);
    footerstring =  'No connection to ' + ws_address;
    footerstring += '.<br>Attempting reconnect in ' + timeout/1000 + ' s...' + e.reason;
    footerstring += '<br>Tap to change address.'
    document.getElementById("users").innerHTML = "";
    document.getElementById("ip").innerHTML = footerstring;

    document.querySelectorAll('.displayBlock').forEach(function (div) {
      div.remove();
    });
    setTimeout (connect, Math.min(5000, timeout) );

    no_data = '{"actuator_state": {\
        "throttle": {"pos":"?", "nmt_state":"No connection", "motion_state":"State unknown"},\
        "brake": {"pos":"?", "nmt_state":"No connection", "motion_state":"State unknown"},\
        "steering": {"pos":"?", "nmt_state":"No connection", "motion_state":"State unknown"}\
    }}';
    document.getElementById("config-button").disabled = true;
    message_handler(no_data);
  };

  ws.onerror = function(err) {
    console.error('Socket encountered error: ', err.message, 'Closing socket');
    ws.close();
  };
}

function close_window() {
  const shouldClose = confirm("Are you sure you want to exit the UI?");
  if (shouldClose) {
    // Try to close the window
    window.close();
  }
}

var config

var control_mode;
var steering_pos;
var throttle_pos;
var brake_pos;

const steering_g = document.getElementById("steering-gauge");
const throttle_g = document.getElementById("throttle-gauge");
const brake_g = document.getElementById("brake-gauge");

const e_steering_val = document.getElementById("steering-val");
const e_throttle_val = document.getElementById("throttle-val");
const e_brake_val = document.getElementById("brake-val");

const e_steering_nmt = document.getElementById("steering-nmt");
const e_throttle_nmt = document.getElementById("throttle-nmt");
const e_brake_nmt = document.getElementById("brake-nmt");

const e_steering_runstate = document.getElementById("steering-runstate");
const e_throttle_runstate = document.getElementById("throttle-runstate");
const e_brake_runstate = document.getElementById("brake-runstate");

function init() {
  document.getElementById("config-button").onclick = function () { send_mode_change(); };
  document.getElementById("disable-button").onclick = function () { toggle_disable_control(); };

  document.getElementById("steering-p90").onclick = function () { manual_drive('steering', Number(steering_pos) + 90); };
  document.getElementById("steering-p10").onclick = function () { manual_drive('steering', Number(steering_pos) + 10); };
  document.getElementById("steering-0").onclick = function () { manual_drive('steering', 0); };
  document.getElementById("steering-n10").onclick = function () { manual_drive('steering', Number(steering_pos) - 10); };
  document.getElementById("steering-n90").onclick = function () { manual_drive('steering', Number(steering_pos) - 90); };

  document.getElementById("steering-set-max").onclick = function () { send_command('steering', 'set-max', Number(steering_pos).toFixed(0)); };
  document.getElementById("steering-set-zero").onclick = function () { send_command('steering', 'set-zero', Number(steering_pos).toFixed(0)); };
  document.getElementById("steering-set-min").onclick = function () { send_command('steering', 'set-min', Number(steering_pos).toFixed(0)); };

  document.getElementById("throttle-p20").onclick = function () { manual_drive('throttle', Number(throttle_pos) + 20); };
  document.getElementById("throttle-p2").onclick = function () { manual_drive('throttle', Number(throttle_pos) + 2); };
  document.getElementById("throttle-n2").onclick = function () { manual_drive('throttle', Number(throttle_pos) - 2); };
  document.getElementById("throttle-n20").onclick = function () { manual_drive('throttle', Number(throttle_pos) - 20); };

  document.getElementById("throttle-set-max").onclick = function () { send_command('throttle', 'set-max', Number(throttle_pos).toFixed(0)); };
  document.getElementById("throttle-set-min").onclick = function () { send_command('throttle', 'set-min', Number(throttle_pos).toFixed(0)); };

  document.getElementById("throttle-stop").onclick = function () { send_command('throttle', 'stop'); };
  document.getElementById("throttle-clear").onclick = function () { send_command('throttle', 'clear'); };

  document.getElementById("brake-p20").onclick = function () { manual_drive('brake', Number(brake_pos) + 20); };
  document.getElementById("brake-p2").onclick = function () { manual_drive('brake', Number(brake_pos) + 2); };
  document.getElementById("brake-n2").onclick = function () { manual_drive('brake', Number(brake_pos) - 2); };
  document.getElementById("brake-n20").onclick = function () { manual_drive('brake', Number(brake_pos) - 20); };

  document.getElementById("brake-set-max").onclick = function () { send_command('brake', 'set-max', Number(brake_pos).toFixed(0)); };
  document.getElementById("brake-set-min").onclick = function () { send_command('brake', 'set-min', Number(brake_pos).toFixed(0)); };

  document.getElementById("brake-stop").onclick = function () { send_command('brake', 'stop'); };
  document.getElementById("brake-clear").onclick = function () { send_command('brake', 'clear'); };
}

document.getElementById("steering-gamma").oninput = function() {
  steering_gamma = Number(this.value).toFixed(1);
  document.getElementById("steering-gamma-val").innerHTML = Number(this.value).toFixed(1);
  localStorage.setItem('steering_gamma', steering_gamma);
}

document.getElementById("throttle-gamma").oninput = function() {
  throttle_gamma = Number(this.value).toFixed(1);
  document.getElementById("throttle-gamma-val").innerHTML = throttle_gamma;
  localStorage.setItem('throttle_gamma', throttle_gamma);
}

document.getElementById("brake-gamma").oninput = function() {
  brake_gamma = Number(this.value).toFixed(1);
  document.getElementById("brake-gamma-val").innerHTML = brake_gamma;
  localStorage.setItem('brake_gamma', brake_gamma);
}

// Even though the buttons that trigger this are incremental, the request is always sent as absolute position.
// This is to prevent repeat sends (network issues, accidental doubleclick, etc) from causing the actuator to move more than intended.
function manual_drive(actuator, position) {
  if (ws.readyState == WebSocket.OPEN && control_mode == 'Config') {
    ws.send(JSON.stringify({'control_request': {'actuator': actuator, 'position': position}}));
  }
}

function send_command(actuator, command, value = None) {
  console.log(actuator, command);
  if (ws.readyState == WebSocket.OPEN) {
    ws.send(JSON.stringify({'command': {'actuator': actuator, 'command': command, 'value': value}}));
  }
}

var controller_disable = true;

function toggle_disable_control() {
  if (controller_disable == true) {
    disable_control(false);
  } else {
    disable_control(true);
  }
}

function disable_control(disabled) {
  console.log(disabled)
  if (disabled) {
    controller_disable = true;
    document.getElementById("disable-text").classList.remove("hidden");
    document.getElementById("disable-button").innerHTML = "Enable Control";
    console.log("Control Disabled");
  } else {
    controller_disable = false;
    document.getElementById("disable-text").classList.add("hidden");
    document.getElementById("disable-button").innerHTML = "Disable Control";
    console.log("Control Enabled");
  }
}

function send_mode_change() {
  if (control_mode == 'Normal') {
    disable_control(true);
    ws.send(JSON.stringify({'mode_change': 'Config'}));
  } else if (control_mode == 'Config') {
    disable_control(false);
    ws.send(JSON.stringify({'mode_change': 'Normal'}));
  }
}

var cfg_e = document.querySelectorAll(".config-e");

function change_control_mode() {
  if (control_mode == 'Normal') {
    cfg_e.forEach(function(el){
      el.classList.add("hidden");
      document.getElementById('config-button').innerHTML = "Config Mode";
    });

  } else if (control_mode == 'Config') {
    cfg_e.forEach(function(el){
      el.classList.remove("hidden");
      document.getElementById('config-button').innerHTML = "Exit Config Mode";
    });
  }
}

function message_handler(data) {
  const event = JSON.parse(data);
  if ('config' in event){
    console.log("Received Config form host")
    config = event.config; // Copy to local variable to be used when changing config params via GUI.
    control_mode = event.control_mode
    document.getElementById("config-button").disabled = false;
    change_control_mode();

    // Shown values always based on event received from host, not local copy to avoid desync when local copy changes.
    steering_g.setAttribute("min", event.config.limits.steering_min);
    steering_g.setAttribute("max", event.config.limits.steering_max);
    document.getElementById("steering-min-val").innerHTML = event.config.limits.steering_min;
    document.getElementById("steering-max-val").innerHTML = event.config.limits.steering_max;

    throttle_g.setAttribute("min", event.config.limits.throttle_min);
    throttle_g.setAttribute("max", event.config.limits.throttle_max);
    document.getElementById("throttle-min-val").innerHTML = event.config.limits.throttle_min;
    document.getElementById("throttle-max-val").innerHTML = event.config.limits.throttle_max;

    brake_g.setAttribute("min", event.config.limits.brake_min);
    brake_g.setAttribute("max", event.config.limits.brake_max);
    document.getElementById("brake-min-val").innerHTML = event.config.limits.brake_min;
    document.getElementById("brake-max-val").innerHTML = event.config.limits.brake_max;

  } else if ("actuator_state" in event) {
    if (control_mode != event.control_mode) {
      control_mode = event.control_mode;
      change_control_mode();
    }

    try {
      steering_pos = event.actuator_state.steering.pos.toFixed(0);
      throttle_pos = event.actuator_state.throttle.pos.toFixed(0);
      brake_pos = event.actuator_state.brake.pos.toFixed(0);
    } catch {
      steering_pos = "?";
      throttle_pos = "?";
      brake_pos = "?";
    }

    // Update gauges with new states
    steering_g.setAttribute("value", steering_pos);
    e_steering_val.innerHTML = steering_pos;

    throttle_g.setAttribute("value", throttle_pos);
    e_throttle_val.innerHTML = throttle_pos;

    brake_g.setAttribute("value", brake_pos);
    e_brake_val.innerHTML = brake_pos;

    e_steering_nmt.innerHTML = event.actuator_state.steering.nmt_state;
    e_throttle_nmt.innerHTML = event.actuator_state.throttle.nmt_state;
    e_brake_nmt.innerHTML = event.actuator_state.brake.nmt_state;

    e_steering_runstate.innerHTML = event.actuator_state.steering.motion_state;
    e_throttle_runstate.innerHTML = event.actuator_state.throttle.motion_state;
    e_brake_runstate.innerHTML = event.actuator_state.brake.motion_state;
  } else if ("clients" in event) {
    const users = `${event.clients} user${event.clients == 1 ? " " : "s "}`;
    document.getElementById("users").innerHTML = users;
  } else {
    console.error("Received unsupported event", event);
  };
};

// Get the modal
var modal = document.getElementById("controller-modal");
// Get the button that opens the modal
var btn = document.getElementById("cfg-button");
// Get the <span> element that closes the modal
var span = document.getElementsByClassName("close")[0];
// When the user clicks on the button, open the modal
btn.onclick = function() {
  modal.style.display = "block";
  disable_control(true);
}
// When the user clicks on <span> (x), close the modal
span.onclick = function() {
  modal.style.display = "none";
  disable_control(false);
}
// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
    disable_control(false);
  }
} 



// Gamepad code
var haveEvents = 'GamepadEvent' in window;
var haveWebkitEvents = 'WebKitGamepadEvent' in window;
var controllers = {};
var rAF = window.mozRequestAnimationFrame ||
  window.webkitRequestAnimationFrame ||
  window.requestAnimationFrame;

function connecthandler(e) {
  addgamepad(e.gamepad);
}

var steering_selector = document.getElementById("steering-selector");
var throttle_selector = document.getElementById("throttle-selector");
var brake_selector = document.getElementById("brake-selector");

steering_selector.onchange = function() {
  steering_axis = Number(this.value);
  localStorage.setItem('steering_axis', steering_axis);
}
throttle_selector.onchange = function() {
  throttle_axis = Number(this.value);
  localStorage.setItem('throttle_axis', throttle_axis);
}
brake_selector.onchange = function() {
  brake_axis = Number(this.value);
  localStorage.setItem('brake_axis', brake_axis);
}

function addgamepad(gamepad) {
  controllers[gamepad.index] = gamepad; 

  var c = document.getElementById("controllers");

  var d = document.createElement("div");
  d.setAttribute("id", "controller" + gamepad.index);
  c.appendChild(d);

  var t = document.createElement("span");
  t.appendChild(document.createTextNode("Gamepad: " + gamepad.id));
  d.appendChild(t);

  /* Buttons disabled for now as there's no use for them yet. See also in updateStatus
  var b = document.createElement("div");
  b.className = "buttons";

  for (var i=0; i<gamepad.buttons.length; i++) {
    var e = document.createElement("span");
    e.className = "button";
    //e.id = "b" + i;
    e.innerHTML = i;
    b.appendChild(e);
  }

  d.appendChild(b);
  */

  // Create axis display meters
  var a = document.createElement("div");
  a.className = "axes";
  for (i=0; i<gamepad.axes.length; i++) {
    // Add visualizers to modal
    axis_container = document.createElement("div");
    axis_container.setAttribute("class", "axis_container");
    axis_container.innerHTML=i + ":";
    e = document.createElement("meter");
    e.className = "axis";
    e.id = "a" + i;
    e.setAttribute("min", "-1");
    e.setAttribute("max", "1");
    e.setAttribute("value", "0");
    e.innerHTML = i;
    axis_container.appendChild(e);
    a.appendChild(axis_container);

    // Populate dropdowns
    var opt_s = document.createElement("option");
    opt_s.value = i;
    opt_s.innerHTML = i;
    steering_selector.appendChild(opt_s);
    if (i == localStorage.getItem('steering_axis')) {
      steering_selector.options[i].selected = true;
    }
    var opt_t = document.createElement("option");
    opt_t.value = i;
    opt_t.innerHTML = i;
    throttle_selector.appendChild(opt_t);
    if (i == localStorage.getItem('throttle_axis')) {
      throttle_selector.options[i].selected = true;
    }
    var opt_b = document.createElement("option");
    opt_b.value = i;
    opt_b.innerHTML = i;
    brake_selector.appendChild(opt_b);
    if (i == localStorage.getItem('brake_axis')) {
      brake_selector.options[i].selected = true;
    }

  }
  d.appendChild(a);
  document.getElementById("start").style.display = "none";

  rAF(updateStatus);
}

function disconnecthandler(e) {
  removegamepad(e.gamepad);
}

function removegamepad(gamepad) {
  var d = document.getElementById("controller" + gamepad.index);
  document.body.removeChild(d);
  delete controllers[gamepad.index];
}

function updateStatus() {
  scangamepads();

  // Update webview
  for (j in controllers) {
    var controller = controllers[j];

    if (ws.readyState == ws.OPEN && !controller_disable) {
      //ws.send(JSON.stringify({ action: "control_input", id: controller.id, axes: controller.axes, buttons: controller.buttons}));
      //ws.send(JSON.stringify({"control_input": {'axes': controller.axes, 'buttons': controller.buttons}}));
      ws.send(JSON.stringify({"control_input": {
        'steering': Math.sign(controller.axes[steering_axis]) * Math.pow(Math.abs(controller.axes[steering_axis]), steering_gamma), //Map from -1..1 to 0..1, apply gamma, map back to -1..1
        'throttle': Math.pow(controller.axes[throttle_axis]+1, throttle_gamma)-1, //Map from -1..1 to 0..2, apply gamma, map back to -1..1 
        'brake': Math.pow(controller.axes[brake_axis]+1, brake_gamma)-1,
      }}))
    }

    var d = document.getElementById("controller" + j);

    /* // Buttons disabled for now as there's no use. See also in addgamepad
    // Loop through buttons and check state
    var buttons = d.getElementsByClassName("button");
    for (var i=0; i<controller.buttons.length; i++) {
      var b = buttons[i];
      var val = controller.buttons[i];
      b.className = "button";
      if (val.pressed) {
        b.className += " pressed"
      }
    }
    */

    // Loop through axis and check state
    var axes = d.getElementsByClassName("axis");
    for (var i=0; i<controller.axes.length; i++) {
      var a = axes[i];
      a.innerHTML = i + ": " + controller.axes[i].toFixed(4);
      a.setAttribute("value", controller.axes[i]);
    }

  }
  rAF(updateStatus);
}

function scangamepads() {
  var gamepads = navigator.getGamepads ? navigator.getGamepads() : (navigator.webkitGetGamepads ? navigator.webkitGetGamepads() : []);
  for (var i = 0; i < gamepads.length; i++) {
    if (gamepads[i] && (gamepads[i].index in controllers)) {
      controllers[gamepads[i].index] = gamepads[i];
    }
  }
}

if (haveEvents) {
  window.addEventListener("gamepadconnected", connecthandler);
  window.addEventListener("gamepaddisconnected", disconnecthandler);
} else if (haveWebkitEvents) {
  window.addEventListener("webkitgamepadconnected", connecthandler);
  window.addEventListener("webkitgamepaddisconnected", disconnecthandler);
} else {
  setInterval(scangamepads, 500);
}