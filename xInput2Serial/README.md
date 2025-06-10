#### Overview

The **XInput to Serial Converter** application maps Xbox controller inputs 
to a USB-serial device that the Nintendo Switch recognizes as a Pro Controller. 
This Python-only implementation is headless and uses the native XInput API on Windows.

#### Features

- **Persistent 100 Hz streaming:** Sends controller or neutral packets continuously 
  to prevent the firmware failsafe from closing the input when no user commands are issued.  
- **Window title binding:** Only streams packets when a specified window is active (requires `pywin32`).  
- **Auto-detection:** Finds and connects to the first available COM or HIDAPI port and Xbox controller.
- **Manual selection:** Specify COM or HID port and controller slot on the command line.
- **Native XInput backend:** Uses `ctypes` to call the Windows XInput API directly—no SDL or other frameworks required.  
- **Failsafe support:** If the controller disconnects, or the serial link breaks, the Switch will pause or return to the HOME menu per built-in firmware logic.

#### Requirements

- Python 3.10+
  - `pyserial`
  - `hid` (only if using HIDAPI devices)
  - `pywin32` (only if using `--window`)
- Windows 10 or later

#### Usage

```bash
cd xInput-Switch/xInput2Serial/python_version
python xinput2serial.py [options]
```

##### Options

- `--auto`                 Auto-select first COM or HID port and controller
- `--port COMx|hid:path`   Specify a COM port or HID path
- `--baud N`               Set baud rate (default: 1_000_000)  
- `--controller N`         Specify XInput controller slot (0–3, default: 0)
- `--window "TITLE"`       Only stream while window is active (requires `pywin32`)  
- `--debug`                Print detected devices, raw input values, and every transmitted packet  

##### Examples

```bash
python xinput2serial.py --auto --window "OBS (Preview)" --debug
```

#### Wiring

Connect your CH340-based USB-serial adapter directly to the controller firmware board:

- TX → TX  
- RX → RX  
- 5 V → 5 V  
- GND → GND  

The CH340 handles level shifting; no crossover is needed.

#### Troubleshooting

- If the Switch fails to detect the controller, power-cycle the dock and retry.  
- Ensure your target window title matches exactly (case insensitive).  
- Use `--debug` to verify packet data and timing.
