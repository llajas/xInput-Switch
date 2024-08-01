package com.example;

import com.studiohartman.jamepad.ControllerManager;

public class JamepadManager {

    private ControllerManager controllers;

    public JamepadManager() {
        controllers = new ControllerManager();
        controllers.initSDLGamepad();
    }

    public void update() {
        controllers.update();
    }

    public void close() {
        controllers.quitSDLGamepad();
    }

    public ControllerManager getControllers() {
        return controllers;
    }
}
