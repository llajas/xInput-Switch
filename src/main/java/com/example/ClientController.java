package com.example;

import com.studiohartman.jamepad.ControllerAxis;
import com.studiohartman.jamepad.ControllerButton;
import com.studiohartman.jamepad.ControllerIndex;
import com.studiohartman.jamepad.ControllerUnpluggedException;

import java.io.IOException;

public class ClientController {
    private final SerialAdapter serialAdapter;
    private final ControllerIndex controllerIndex;

    public ClientController(SerialAdapter serialAdapter, ControllerIndex controllerIndex) {
        this.serialAdapter = serialAdapter;
        this.controllerIndex = controllerIndex;
    }

    public void start() {
        new Thread(() -> {
            while (true) {
                try {
                    Packet packet = new Packet(
                            new Packet.Buttons(code -> {
                                try {
                                    return isButtonPressed(controllerIndex, code);
                                } catch (ControllerUnpluggedException e) {
                                    e.printStackTrace();
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
                    e.printStackTrace();
                    break;
                }
            }
        }).start();
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
