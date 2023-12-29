# Refactored Nintendo Switch Remote Control Application

## Description

This application is a refactored version of the original Nintendo Switch Remote Control project. The original project used WebRTC for real-time communication between a client and server application. This refactored application is designed to run entirely locally without a client-server setup.

The purpose of this application is to enable local communication with a Nintendo Switch controller. It allows users to select an input device, and sends commands from that device to a serial port connected to a microcontroller. The microcontroller then communicates with the Nintendo Switch.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Credits](#credits)
- [License](#license)

## Installation

To install this application, clone the repository and build it using Gradle:

```bash
git clone https://github.com/llajas/xInput-Switch.git cd xInput-Switch ./gradlew build
```

## Usage

After building the application, you can run it with the following command:

```bash
 ./gradlew run
```

The application will display a GUI where you can select an input device and set the baud rate for the serial connection. After setting these options, click the "Connect" button to establish a connection with the microcontroller.

## Credits

This application is a refactored version of the original Nintendo Switch Remote Control project by javmarina. The original project can be found at [https://github.com/javmarina/Nintendo-Switch-Remote-Control](https://github.com/javmarina/Nintendo-Switch-Remote-Control).

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
