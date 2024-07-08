package com.example;

import javafx.application.Application;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.control.TextFormatter;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;
import javafx.util.StringConverter;
import com.fazecast.jSerialComm.SerialPort;

import java.util.function.UnaryOperator;
import java.util.prefs.Preferences;
import java.util.regex.Pattern;

public class Main extends Application {

    private static final Pattern NUMERIC_PATTERN = Pattern.compile("[0-9]*");
    private static final int DEFAULT_BAUDRATE = 1000000; // Default baud rate (1 Mbps)
    private static final int MAX_BAUDRATE = 1000000;
    private static final int MIN_BAUDRATE = 9600;
    private static final String KEY_BAUDRATE = "key_baudrate";

    private final Preferences prefs = Preferences.userNodeForPackage(Main.class);

    private TextField baudrateField;
    private ComboBox<SerialPort> serialPortComboBox;
    private Button connectButton;
    private Label statusLabel;

    @Override
    public void start(Stage primaryStage) {
        primaryStage.setTitle("XInput to Serial Converter");

        serialPortComboBox = new ComboBox<>();
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
                    || serialPortComboBox.getValue() == null;
        }, baudrateField.textProperty(), serialPortComboBox.valueProperty()));

        connectButton.setOnAction(e -> connectToSerialPort());

        VBox vbox = new VBox(serialPortComboBox, baudrateField, connectButton, statusLabel);
        Scene scene = new Scene(vbox, 300, 200);
        primaryStage.setScene(scene);
        primaryStage.show();
    }

    private void connectToSerialPort() {
        SerialPort selectedPort = serialPortComboBox.getValue();
        int baudRate = Integer.parseInt(baudrateField.getText());

        try {
            selectedPort.openPort();
            selectedPort.setBaudRate(baudRate);
            selectedPort.setNumDataBits(8); // Use appropriate constants for jSerialComm 2.9.1
            selectedPort.setNumStopBits(SerialPort.ONE_STOP_BIT); // Use appropriate constants for jSerialComm 2.9.1
            selectedPort.setParity(SerialPort.NO_PARITY);
            statusLabel.setText("Connected to " + selectedPort.getSystemPortName() + " at " + baudRate + " baud.");
        } catch (Exception e) {
            statusLabel.setText("Failed to connect: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        launch(args);
    }
}