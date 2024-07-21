package com.example;

import com.studiohartman.jamepad.ControllerAxis;
import com.studiohartman.jamepad.ControllerButton;
import com.studiohartman.jamepad.ControllerIndex;
import com.studiohartman.jamepad.ControllerManager;
import com.studiohartman.jamepad.ControllerUnpluggedException;
import javafx.application.Platform;
import javafx.scene.control.Label;

import java.io.IOException;
import java.util.logging.Logger;
import com.sun.jna.Native;
import com.sun.jna.platform.win32.User32;
import com.sun.jna.platform.win32.WinDef;

public class ClientController {
    private final SerialAdapter serialAdapter;
    private final ControllerManager controllerManager;
    private ControllerIndex controllerIndex;
    private static final Logger logger = Logger.getLogger(ClientController.class.getName());
    private volatile boolean running = true;
    private volatile boolean obsActive = true; // Default to true
    private final Label receivedBytesLabel;
    private final String windowTitle;

    // Constructor for GUI mode
    public ClientController(SerialAdapter serialAdapter, ControllerManager controllerManager, ControllerIndex controllerIndex, Label receivedBytesLabel, String windowTitle) {
        this.serialAdapter = serialAdapter;
        this.controllerManager = controllerManager;
        this.controllerIndex = controllerIndex;
        this.receivedBytesLabel = receivedBytesLabel;
        this.windowTitle = windowTitle;
    }

    // Constructor for CLI mode
    public ClientController(SerialAdapter serialAdapter, ControllerManager controllerManager, ControllerIndex controllerIndex, String windowTitle) {
        this(serialAdapter, controllerManager, controllerIndex, null, windowTitle);
    }

    public void start() {
        new Thread(() -> {
            while (running) {
                if (isWindowActive(windowTitle)) {
                    try {
                        Packet packet = new Packet(
                                new Packet.Buttons(code -> {
                                    try {
                                        return isButtonPressed(controllerIndex, code);
                                    } catch (ControllerUnpluggedException e) {
                                        logger.warning("Controller disconnected. Attempting to reconnect...");
                                        reconnectController();
                                        return false;
                                    }
                                }),
                                mapToDpad(controllerIndex),
                                new Packet.Joystick(controllerIndex.getAxisState(ControllerAxis.LEFTX), controllerIndex.getAxisState(ControllerAxis.LEFTY)),
                                new Packet.Joystick(controllerIndex.getAxisState(ControllerAxis.RIGHTX), controllerIndex.getAxisState(ControllerAxis.RIGHTY))
                        );
                        byte[] buffer = packet.getBuffer();
                        serialAdapter.write(buffer);
                        if (receivedBytesLabel != null) {
                            Platform.runLater(() -> receivedBytesLabel.setText(SerialAdapter.byteArrayToHex(buffer)));
                        }
                        Thread.sleep(10);
                    } catch (ControllerUnpluggedException | IOException | InterruptedException e) {
                        logger.severe("Error in main loop: " + e.getMessage());
                        e.printStackTrace();
                        break;
                    }
                } else {
                    try {
                        Thread.sleep(100); // Poll less frequently when the window is not active
                    } catch (InterruptedException e) {
                        e.printStackTrace();
                        break;
                    }
                }
            }
            serialAdapter.close();  // Ensure the serial port is closed when the thread stops
        }).start();

        new Thread(() -> {
            byte[] buffer = new byte[1024];
            while (running) {
                try {
                    int bytesRead = serialAdapter.read(buffer);
                    if (bytesRead > 0) {
                        logger.fine("Read from serial: " + SerialAdapter.byteArrayToHex(buffer, bytesRead));
                    }
                    Thread.sleep(100);
                } catch (IOException | InterruptedException e) {
                    logger.severe("Error in serial read loop: " + e.getMessage());
                    e.printStackTrace();
                    break;
                }
            }
            serialAdapter.close();  // Ensure the serial port is closed when the thread stops
        }).start();
    }

    public void setOBSActive(boolean obsActive) {
        this.obsActive = obsActive;
    }

    private boolean isWindowActive(String windowTitle) {
        User32 user32 = User32.INSTANCE;
        WinDef.HWND hwnd = user32.GetForegroundWindow();
        char[] windowText = new char[512];
        user32.GetWindowText(hwnd, windowText, 512);
        String currentWindowTitle = Native.toString(windowText);
        return windowTitle.equals(currentWindowTitle);
    }

    private void reconnectController() {
        while (running) {
            controllerManager.update();
            for (int i = 0; i < controllerManager.getNumControllers(); i++) {
                ControllerIndex newController = controllerManager.getControllerIndex(i);
                try {
                    if (newController.isConnected()) {
                        controllerIndex = newController;
                        logger.info("Reconnected to controller: " + newController.getName());
                        return;
                    }
                } catch (ControllerUnpluggedException e) {
                    logger.warning("Controller at index " + i + " is not connected: " + e.getMessage());
                }
            }
            try {
                Thread.sleep(1000); // wait for a second before trying again
            } catch (InterruptedException e) {
                logger.severe("Reconnection sleep interrupted: " + e.getMessage());
                Thread.currentThread().interrupt();
            }
        }
    }

    public void stop() {
        running = false;
    }

    protected static boolean isButtonPressed(final ControllerIndex controller, final Packet.Buttons.Code code)
            throws ControllerUnpluggedException {
        switch (code) {
            case Y: return controller.isButtonPressed(ControllerButton.X);
            case B: return controller.isButtonPressed(ControllerButton.A);
            case A: return controller.isButtonPressed(ControllerButton.B);
            case X: return controller.isButtonPressed(ControllerButton.Y);
            case L: return controller.isButtonPressed(ControllerButton.LEFTBUMPER);
            case R: return controller.isButtonPressed(ControllerButton.RIGHTBUMPER);
            case ZL: return controller.getAxisState(ControllerAxis.TRIGGERLEFT) > 0.5f;
            case ZR: return controller.getAxisState(ControllerAxis.TRIGGERRIGHT) > 0.5f;
            case MINUS: return controller.isButtonPressed(ControllerButton.BACK);
            case PLUS: return controller.isButtonPressed(ControllerButton.START);
            case LCLICK: return controller.isButtonPressed(ControllerButton.LEFTSTICK);
            case RCLICK: return controller.isButtonPressed(ControllerButton.RIGHTSTICK);
            case HOME: return controller.isButtonPressed(ControllerButton.GUIDE);
            case CAPTURE:
            case NONE:
            default:
                return false;
        }
    }

    private Packet.Dpad mapToDpad(ControllerIndex controllerIndex) throws ControllerUnpluggedException {
        return new Packet.Dpad(
                controllerIndex.isButtonPressed(ControllerButton.DPAD_UP),
                controllerIndex.isButtonPressed(ControllerButton.DPAD_RIGHT),
                controllerIndex.isButtonPressed(ControllerButton.DPAD_DOWN),
                controllerIndex.isButtonPressed(ControllerButton.DPAD_LEFT)
        );
    }
}
