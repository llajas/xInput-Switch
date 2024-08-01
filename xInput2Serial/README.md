#### Overview

The **XInput to Serial Converter** Java application is designed to map controller inputs to a serial device. It supports various controller types, including Xbox and PlayStation controllers and is capable of running in headless mode. The application also allows specifying a particular window title, ensuring that controller inputs are sent only when a specific window is active.

#### Features

- **Headless Mode:** The application can run without a graphical user interface, suitable for automated or background processes.
- **Window Title Binding:** Controller inputs are directed to a serial device only when a specified window is active.
- **Auto-Detection:** Automatically detects and connects to the first available serial port and controller.

#### Requirements

- Java 17 or later
- JavaFX library
- Jamepad library for gamepad support
- JNA library for interacting with native OS features

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

##### Options

- `--headless`: Run the application without a GUI.
- `--auto`: Automatically select the first available serial port and controller.
- `--window "Window Title"`: Specify the window title to bind controller inputs.

##### Example

```bash
java -jar xinput-serial-1.0-SNAPSHOT.jar --headless --auto --window "Fullscreen Projector (Preview)"
```

This command starts the application in headless mode, auto-selects the first available serial port and controller, and binds inputs only when the window titled "Fullscreen Projector (Preview)" is active, in this case OBS streaming software. This can be substituted for any other application.

#### Source Code Structure

- **Main.java**: The main entry point of the application. It initializes the GUI or runs in headless mode based on arguments.
- **ClientController.java**: Manages the connection between the controller inputs and the serial device.
- **SerialAdapter.java**: Handles communication with the serial device.
- **JamepadManager.java**: Manages the connection to gamepads using the Jamepad library.