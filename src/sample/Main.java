package sample;

import com.fazecast.jSerialComm.SerialPort;
import javafx.application.Application;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.*;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;
import server.SerialAdapter;
import client.services.DefaultJamepadService;
import client.JamepadManager;
import java.util.ArrayList;

import java.io.IOException;

public class Main extends Application {
    @Override
    public void start(Stage primaryStage) {
        ComboBox<SerialPort> comPortComboBox = new ComboBox<>();
        comPortComboBox.getItems().addAll(SerialPort.getCommPorts());

        TextField baudRateTextField = new TextField();
        baudRateTextField.setText("9600"); // Default baud rate

        ChoiceBox<DefaultJamepadService> inputDeviceDropdown = new ChoiceBox<>();
        ArrayList<DefaultJamepadService> inputDevices = JamepadManager.getAvailableJamepadServices();
        inputDeviceDropdown.getItems().addAll(inputDevices);

        inputDeviceDropdown.setOnAction(event -> {
            DefaultJamepadService selectedDevice = inputDeviceDropdown.getValue();
            // Handle the selected device
        });

        Button connectButton = new Button("Connect");
        connectButton.setOnAction(event -> {
            // Get the selected COM port, baud rate, and input device
            SerialPort selectedPort = comPortComboBox.getValue();
            int baudRate = Integer.parseInt(baudRateTextField.getText());
            DefaultJamepadService selectedDevice = inputDeviceDropdown.getValue();

            // Create a SerialAdapter object
            SerialAdapter serialAdapter = new SerialAdapter(selectedPort, baudRate);

            // Synchronize with the Arduino
            try {
                serialAdapter.sync(false);
            } catch (IOException e) {
                e.printStackTrace();
                return;
            }

            // TODO: Send packets to the Arduino using the serialAdapter object
            // For example:
            // Packet packet = new Packet(...); // Create a Packet object
            // serialAdapter.sendPacket(packet); // Send the packet to the Arduino
        });

        VBox vbox = new VBox(10);
        vbox.setAlignment(Pos.CENTER);
        vbox.getChildren().addAll(new Label("COM Port:"), comPortComboBox, new Label("Baud Rate:"), baudRateTextField, new Label("Input Device:"), inputDeviceDropdown, connectButton);

        Scene scene = new Scene(vbox, 200, 150);
        primaryStage.setTitle("Connect to Arduino");
        primaryStage.setScene(scene);
        primaryStage.show();
    }

    public static void main(String[] args) {
        launch(args);
    }
}
