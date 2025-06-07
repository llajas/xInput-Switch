#### Overview

The **XInput to Serial Converter** application maps controller inputs to a serial device.  Originally written in Java, a light‑weight Python version is also provided for Windows users.  Both variants can run headless and optionally bind input to a specific window.

#### Features

- **Headless Mode:** The application can run without a graphical user interface, suitable for automated or background processes.
- **Window Title Binding:** Controller inputs are directed to a serial device only when a specified window is active.
- **Auto-Detection:** Automatically detects and connects to the first available serial port and controller.
- **Defaults:** When run with `--auto`, the first detected controller and COM port are used with a baud rate of 1&nbsp;000&nbsp;000 (1&nbsp;Mbps).
- **Raw Input Support:** On Windows, the Python script sets `SDL_JOYSTICK_RAWINPUT=1` so virtual devices like Moonlight's "RAW INPUT" controller are detected.
- **Direct XInput Backend:** When running on Windows, controller input is read using the native XInput API for reliable button updates.
- **Headless Operation:** `SDL_VIDEODRIVER` is set to `dummy` so the Python version runs without opening a window on any platform.

#### Requirements

- Java 17 or later
- JavaFX library
- Jamepad library for gamepad support
- JNA library for interacting with native OS features
- Python 3.10 or later (for the optional Python implementation)
- `pyserial` and `inputs` libraries
 - `pywin32` on Windows if the `--window` option will be used

#### Building the Package

To build the package, ensure all dependencies are correctly added to your `pom.xml` and follow these steps:

1. Open a terminal and navigate to the project directory.
2. Run the following Maven command to clean and package the project:

    ```bash
    mvn clean package
    ```

This command will compile the source code, run tests, and package the application into a JAR file located in the `target` directory.

#### Usage

To run the application, use the following command:

```bash
java -jar xinput-serial-1.0-SNAPSHOT.jar [options]
```

Alternatively, a Windows friendly Python script is available under
`python_version`.  Invoke it with:

```bash
python python_version/xinput2serial.py [options]
```

##### Options

- `--headless`: Run the application without a GUI.
- `--auto`: Automatically select the first available serial port and controller.
 - `--window "Window Title"`: Specify the window title to bind controller inputs (requires `pywin32` on Windows). When the window loses focus, a neutral packet is sent and transmission pauses until the window becomes active again.
- `--port COMx`: Specify a serial port (Python only).
- `--baudrate N`: Set baud rate, defaults to 1,000,000.
- `--debug`: Print detected devices, raw input values, and every transmitted packet.

##### Example

```bash
java -jar xinput-serial-1.0-SNAPSHOT.jar --headless --auto --window "Fullscreen Projector (Preview)"
```

```bash
python python_version/xinput2serial.py --auto --window "Fullscreen Projector (Preview)"
```

This command starts the application in headless mode, auto-selects the first available serial port and controller, and binds inputs only when the window titled "Fullscreen Projector (Preview)" is active, in this case OBS streaming software. This can be substituted for any other application.

#### Source Code Structure

- **Main.java**: The main entry point of the application. It initializes the GUI or runs in headless mode based on arguments.
- **ClientController.java**: Manages the connection between the controller inputs and the serial device.
- **SerialAdapter.java**: Handles communication with the serial device.
- **JamepadManager.java**: Manages the connection to gamepads using the Jamepad library.

#### Wiring

When connecting the CH340 USB-to-serial adapter, wire it directly to the Arduino as follows:

- **TX -> TX**
- **RX -> RX**
- **5V -> 5V**
- **GND -> GND**

The CH340 handles the level conversion, so the signals do not need to be crossed.

#### Troubleshooting

Occasionally the device may not be detected by the Switch. Performing a quick power cycle of the Nintendo Switch dock has proven to restore normal operation.
