package com.example;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.scene.Scene;
import javafx.scene.control.*;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;
import javafx.util.StringConverter;
import com.fazecast.jSerialComm.SerialPort;
import com.studiohartman.jamepad.ControllerIndex;
import com.studiohartman.jamepad.ControllerManager;
import com.studiohartman.jamepad.ControllerUnpluggedException;
import com.sun.jna.Native;
import com.sun.jna.platform.win32.User32;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinDef.HWND;

import java.util.ArrayList;
import java.util.List;
import java.util.function.UnaryOperator;
import java.util.prefs.Preferences;
import java.util.regex.Pattern;
import java.util.logging.Logger;

public class Main extends Application {

    private static final Pattern NUMERIC_PATTERN = Pattern.compile("[0-9]*");
    private static final int DEFAULT_BAUDRATE = 1000000; // Default baud rate (1 Mbps)
    private static final int MAX_BAUDRATE = 1000000;
    private static final int MIN_BAUDRATE = 9600;
    private static final String KEY_BAUDRATE = "key_baudrate";
    private static final Logger logger = Logger.getLogger(Main.class.getName());
    
    private final Preferences prefs = Preferences.userNodeForPackage(Main.class);

    private TextField baudrateField;
    private ComboBox<SerialPort> serialPortComboBox;
    private ComboBox<ControllerIndex> controllerComboBox;
    private ComboBox<String> windowComboBox;
    private Button connectButton;
    private Label statusLabel;

    private final ControllerManager controllerManager = new ControllerManager();
    private SerialAdapter serialAdapter;
    private ClientController clientController;

    private static String[] args;
    private static boolean headless = false;
    private static String selectedWindowTitle = "";

    @Override
    public void start(Stage primaryStage) {
        if (headless) {
            primaryStage.setOpacity(0);
            primaryStage.setIconified(true);
            primaryStage.setAlwaysOnTop(true);
            initGUI(primaryStage);
        } else {
            initGUI(primaryStage);
        }
    }

    private void initGUI(Stage primaryStage) {
        primaryStage.setTitle("XInput to Serial Converter");

        serialPortComboBox = new ComboBox<>();
        controllerComboBox = new ComboBox<>();
        windowComboBox = new ComboBox<>();
        baudrateField = new TextField();
        connectButton = new Button("Connect");
        statusLabel = new Label();

        // Populate COM ports
        SerialPort[] portNames = SerialPort.getCommPorts();
        ObservableList<SerialPort> observableList = FXCollections.observableArrayList(portNames);
        serialPortComboBox.setItems(observableList);
        serialPortComboBox.setConverter(new StringConverter<SerialPort>() {
            @Override
            public String toString(final SerialPort serialPort) {
                return serialPort != null ? serialPort.getSystemPortName() : "None";
            }

            @Override
            public SerialPort fromString(final String string) {
                return serialPortComboBox.getItems().stream()
                        .filter(serialPort -> serialPort.getSystemPortName().equals(string))
                        .findFirst()
                        .orElse(null);
            }
        });

        // Populate controllers
        populateControllers();

        // Populate windows
        populateWindows();

        // Set default baud rate
        baudrateField.setText(prefs.get(KEY_BAUDRATE, String.valueOf(DEFAULT_BAUDRATE)));

        // Force the field to be numeric only
        final UnaryOperator<TextFormatter.Change> integerFilter = change -> {
            final String input = change.getText();
            if (NUMERIC_PATTERN.matcher(input).matches()) {
                return change;
            }
            return null;
        };
        baudrateField.setTextFormatter(new TextFormatter<>(integerFilter));
        baudrateField.textProperty().addListener((observable, oldValue, newValue) -> prefs.put(KEY_BAUDRATE, newValue));

        connectButton.disableProperty().bind(Bindings.createBooleanBinding(() -> {
            if (baudrateField.getText().length() > String.valueOf(MAX_BAUDRATE).length()) {
                return true;
            }
            final int baud = baudrateField.getText().length() == 0 ?
                    0 : Integer.parseInt(baudrateField.getText());
            return baud < MIN_BAUDRATE || baud > MAX_BAUDRATE
                    || serialPortComboBox.getValue() == null
                    || controllerComboBox.getValue() == null
                    || windowComboBox.getValue() == null;
        }, baudrateField.textProperty(), serialPortComboBox.valueProperty(), controllerComboBox.valueProperty(), windowComboBox.valueProperty()));

        connectButton.setOnAction(e -> {
            if ("Connect".equals(connectButton.getText())) {
                selectedWindowTitle = windowComboBox.getValue();
                connectToSerialPort();
            } else {
                primaryStage.close(); // Close the window on disconnect
            }
        });

        VBox vbox = new VBox(serialPortComboBox, controllerComboBox, windowComboBox, baudrateField, connectButton, statusLabel);
        Scene scene = new Scene(vbox, 300, 200);
        primaryStage.setScene(scene);

        primaryStage.setOnCloseRequest(event -> {
            stopApplication();
            Platform.exit();
        });

        primaryStage.show();

        if (args.length > 0) {
            handleArguments(args);
        }
    }

    private void populateControllers() {
        controllerManager.initSDLGamepad();
        ObservableList<ControllerIndex> controllerList = FXCollections.observableArrayList();
        for (int i = 0; i < controllerManager.getNumControllers(); i++) {
            ControllerIndex controllerIndex = controllerManager.getControllerIndex(i);
            if (controllerIndex != null && controllerIndex.isConnected()) {
                controllerList.add(controllerIndex);
            }
        }
        controllerComboBox.setItems(controllerList);
        controllerComboBox.setConverter(new StringConverter<ControllerIndex>() {
            @Override
            public String toString(final ControllerIndex controllerIndex) {
                try {
                    return controllerIndex != null ? controllerIndex.getName() : "None";
                } catch (ControllerUnpluggedException e) {
                    e.printStackTrace();
                    return "Disconnected";
                }
            }

            @Override
            public ControllerIndex fromString(final String string) {
                return controllerComboBox.getItems().stream()
                        .filter(controllerIndex -> {
                            try {
                                return controllerIndex != null && controllerIndex.getName().equals(string);
                            } catch (ControllerUnpluggedException e) {
                                e.printStackTrace();
                                return false;
                            }
                        })
                        .findFirst()
                        .orElse(null);
            }
        });
    }

    private void populateWindows() {
        User32 user32 = User32.INSTANCE;
        List<String> windowTitles = new ArrayList<>();

        user32.EnumWindows((hwnd, pointer) -> {
            char[] windowText = new char[512];
            user32.GetWindowText(hwnd, windowText, 512);
            String wText = Native.toString(windowText);
            if (!wText.isEmpty()) {
                windowTitles.add(wText);
            }
            return true;
        }, null);

        ObservableList<String> observableWindowList = FXCollections.observableArrayList(windowTitles);
        windowComboBox.setItems(observableWindowList);
        windowComboBox.setConverter(new StringConverter<String>() {
            @Override
            public String toString(final String windowTitle) {
                return windowTitle != null ? windowTitle : "None";
            }

            @Override
            public String fromString(final String string) {
                return windowComboBox.getItems().stream()
                        .filter(windowTitle -> windowTitle.equals(string))
                        .findFirst()
                        .orElse(null);
            }
        });
    }

    private void handleArguments(String[] args) {
        final String[] serialPortName = {null};
        final int[] baudRate = {DEFAULT_BAUDRATE};
        final ControllerIndex[] selectedController = {null};
        final String[] selectedWindowTitle = {null};
        final boolean[] useFirstAvailable = {false};

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--port":
                    if (i + 1 < args.length) {
                        serialPortName[0] = args[++i];
                    }
                    break;
                case "--baudrate":
                    if (i + 1 < args.length) {
                        baudRate[0] = Integer.parseInt(args[++i]);
                    }
                    break;
                case "--controller":
                    if (i + 1 < args.length) {
                        String controllerName = args[++i];
                        selectedController[0] = controllerComboBox.getItems().stream()
                                .filter(controllerIndex -> {
                                    try {
                                        return controllerIndex.getName().equals(controllerName);
                                    } catch (ControllerUnpluggedException e) {
                                        e.printStackTrace();
                                        return false;
                                    }
                                })
                                .findFirst()
                                .orElse(null);
                    }
                    break;
                case "--window":
                    if (i + 1 < args.length) {
                        selectedWindowTitle[0] = args[++i];
                    }
                    break;
                case "--auto":
                    useFirstAvailable[0] = true;
                    break;
                case "--headless":
                    headless = true;
                    break;
            }
        }

        if (useFirstAvailable[0]) {
            SerialPort firstAvailablePort = serialPortComboBox.getItems().isEmpty() ? null : serialPortComboBox.getItems().get(0);
            ControllerIndex firstAvailableController = controllerComboBox.getItems().isEmpty() ? null : controllerComboBox.getItems().get(0);
            String firstAvailableWindowTitle = windowComboBox.getItems().isEmpty() ? null : windowComboBox.getItems().get(0);

            if (firstAvailablePort != null && firstAvailableController != null && firstAvailableWindowTitle != null) {
                serialPortComboBox.setValue(firstAvailablePort);
                controllerComboBox.setValue(firstAvailableController);
                windowComboBox.setValue(firstAvailableWindowTitle);
                baudrateField.setText(String.valueOf(baudRate[0]));
                connectToSerialPort();
            } else {
                retryControllerDetection();
            }
        } else if (serialPortName[0] != null && selectedController[0] != null && selectedWindowTitle[0] != null) {
            SerialPort selectedPort = serialPortComboBox.getItems().stream()
                    .filter(port -> port.getSystemPortName().equals(serialPortName[0]))
                    .findFirst()
                    .orElse(null);

            String selectedWindow = windowComboBox.getItems().stream()
                    .filter(window -> window.equals(selectedWindowTitle[0]))
                    .findFirst()
                    .orElse(null);

            if (selectedPort != null && selectedWindow != null) {
                baudrateField.setText(String.valueOf(baudRate[0]));
                serialPortComboBox.setValue(selectedPort);
                controllerComboBox.setValue(selectedController[0]);
                windowComboBox.setValue(selectedWindow);
                connectToSerialPort();
            }
        }
    }

    private void retryControllerDetection() {
        Platform.runLater(() -> {
            controllerManager.initSDLGamepad();
            ObservableList<ControllerIndex> controllerList = FXCollections.observableArrayList();
            for (int i = 0; i < controllerManager.getNumControllers(); i++) {
                ControllerIndex controllerIndex = controllerManager.getControllerIndex(i);
                if (controllerIndex != null && controllerIndex.isConnected()) {
                    controllerList.add(controllerIndex);
                }
            }
            controllerComboBox.setItems(controllerList);
            if (!controllerList.isEmpty()) {
                controllerComboBox.setValue(controllerList.get(0));
            }
        });
    }

    private void connectToSerialPort() {
        SerialPort selectedPort = serialPortComboBox.getValue();
        int baudRate = Integer.parseInt(baudrateField.getText());
        ControllerIndex selectedController = controllerComboBox.getValue();
        selectedWindowTitle = windowComboBox.getValue();

        try {
            selectedPort.setBaudRate(baudRate);
            serialAdapter = new SerialAdapter(selectedPort, baudRate);
            if (serialAdapter.isBaudrateInvalid()) {
                statusLabel.setText("Invalid baud rate for " + selectedPort.getSystemPortName());
                return;
            }
            serialAdapter.sync();
            statusLabel.setText("Connected to " + selectedPort.getSystemPortName() + " at " + baudRate + " baud with controller " + (selectedController != null ? selectedController.getName() : "None") + ".");
            clientController = new ClientController(serialAdapter, controllerManager, selectedController, statusLabel, selectedWindowTitle);
            clientController.start();
            connectButton.setText("Disconnect");
        } catch (Exception e) {
            statusLabel.setText("Failed to connect: " + e.getMessage());
        }
    }

    @Override
    public void stop() throws Exception {
        stopApplication();
        super.stop();
    }

    private void stopApplication() {
        if (clientController != null) {
            clientController.stop();
        }
        if (serialAdapter != null) {
            serialAdapter.close();
        }
        controllerManager.quitSDLGamepad();
    }

    public static void main(String[] args) {
        Main.args = args;
        for (String arg : args) {
            if (arg.equals("--headless")) {
                headless = true;
            }
        }
        launch(args);
    }
}
