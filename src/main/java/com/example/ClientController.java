package com.example;

import com.studiohartman.jamepad.ControllerAxis;
import com.studiohartman.jamepad.ControllerButton;
import com.studiohartman.jamepad.ControllerIndex;
import com.studiohartman.jamepad.ControllerManager;
import com.studiohartman.jamepad.ControllerUnpluggedException;

import java.io.IOException;
import java.util.logging.Logger;

public class ClientController {
    private final SerialAdapter serialAdapter;
    private final ControllerManager controllerManager;
    private ControllerIndex controllerIndex;
    private static final Logger logger = Logger.getLogger(ClientController.class.getName());
    private volatile boolean running = true;

    public ClientController(SerialAdapter serialAdapter, ControllerManager controllerManager, ControllerIndex controllerIndex) {
        this.serialAdapter = serialAdapter;
        this.controllerManager = controllerManager;
        this.controllerIndex = controllerIndex;
    }

    public void start() {
        new Thread(() -> {
            while (running) {
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
                    serialAdapter.write(packet.getBuffer());
                    Thread.sleep(10);
                } catch (ControllerUnpluggedException | IOException | InterruptedException e) {
                    logger.severe("Error in main loop: " + e.getMessage());
                    e.printStackTrace();
                    break;
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
