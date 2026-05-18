#### Overview

The **XInput to Serial Converter** application maps Xbox controller inputs 
to a USB-serial device that the Nintendo Switch recognizes as a Pro Controller. 
This Python-only implementation is headless and uses the native XInput API on Windows.

#### Features

- **Persistent 100 Hz streaming:** Sends controller or neutral packets continuously 
  to prevent the firmware failsafe from closing the input when no user commands are issued.  
- **Window title binding:** Only streams packets when a specified window is active (requires `pywin32`).  
- **Auto-detection:** Finds and connects to the first available COM port and Xbox controller.  
- **Manual selection:** Prompt for COM port and controller slot unless `--auto` is specified.  
- **Native XInput backend:** Uses `ctypes` to call the Windows XInput API directly—no SDL or other frameworks required.  
- **Failsafe support:** If the controller disconnects, or the serial link breaks, the Switch will pause or return to the HOME menu per built-in firmware logic.

#### Requirements

- Python 3.10+  
  - `pyserial`  
  - `pywin32` (only if using `--window`)  
- Windows 10 or later  

#### Usage

```bash
cd xInput-Switch/xInput2Serial/python_version
python xinput2serial.py [options]
```

##### Options

- `--auto`                 Auto-select first COM port and controller  
- `--backend auto|xinput|pygame`
                           Controller backend to use. `xinput` supports Xbox/XInput devices.
                           `pygame` supports SDL-recognized controllers such as DS4.
                           `auto` tries XInput first, then pygame/SDL.
- `--port COMx`            Specify a COM port  
- `--baud N`               Set baud rate (default: 1_000_000)  
- `--controller N`         Specify XInput controller slot (0–3)  
- `--window "TITLE"`       Only stream while window is active (requires `pywin32`)  
- `--debug`                Print detected devices, raw input values, and every transmitted packet  

##### Examples

```bash
python xinput2serial.py --auto --window "OBS (Preview)" --debug
```

##### Sunshine Auto / DS4 manual test

With Moonlight connected and Sunshine's `Emulated Gamepad Type` set to `Auto`, first confirm the bridge can see the controller:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py" --diagnose --backend auto --log-file "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial-backend-diagnose.log"
```

If XInput is unavailable but SDL lists a DS4/Sony controller, test the full bridge without Playnite:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py" --auto --backend pygame --port COM3 --controller 0 --startup-debug --debug --log-file "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial-ds4-manual.log"
```

If you want the bridge to prefer XInput when available and fall back to DS4/SDL, use:

```powershell
py -3 "C:\Nintendo Automation\xInput-Switch\xInput2Serial\xinput2serial.py" --auto --backend auto --port COM3 --startup-debug --debug --log-file "C:\Nintendo Automation\xInput-Switch\Playnite Launcher Scripts\xinput2serial-auto-manual.log"
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
