# OptimalDrive — Drive-By-Wire Remote Control

Browser-based remote control for a drive-by-wire vehicle. Connects to throttle, brake and steering actuators over CAN bus. Supports gamepad input and live actuator feedback.

![Demo](drive.gif)

---

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

---

## Running

**Production** (with CAN hardware connected):
```
docker compose up --build
```

**Development** (no CAN hardware, enables hot reload):
```
DEVELOPMENT=true docker compose up --build
```

Then open `http://localhost` in a browser.

To stop:
```
Ctrl+C
```

---

## DEVELOPMENT flag

| `DEVELOPMENT` | CAN bus | Hot reload |
|---|---|---|
| `false` (default) | enabled | off |
| `true` | disabled | on |

In development mode the backend starts without CAN hardware and the web UI connects normally. All actuators will show "Connection lost" which is expected.

---

## Deploying on the target machine (Raspberry Pi)

`DBW_start.sh` is a convenience script used as a desktop shortcut on the target machine. It starts the Docker containers in a terminal and opens the UI in Firefox kiosk mode automatically.

> **Note:** The path inside `DBW_start.sh` is hardcoded to `/home/optimaldrive/buildtest/DBW`. Update this to match wherever you clone the repo on the target machine.

---

## Gamepad setup

1. Connect a gamepad to the machine running the browser
2. Click **Controller Setup** in the UI
3. Press any button on the gamepad to connect it
4. Assign each axis to steering, throttle and brake using the dropdowns
5. Close the setup panel and click **Enable Control**
