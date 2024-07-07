package server;

import static spark.Spark.*;

import com.google.gson.Gson;
import util.Packet;
import server.SerialAdapter;
import com.fazecast.jSerialComm.SerialPort;

public class Server {

    private static SerialAdapter serialAdapter;
    private static final Gson gson = new Gson();

    public static void main(String[] args) {
        port(8080); // Set the port number for the server

        // Initialize the SerialAdapter with the appropriate COM port and baud rate
        SerialPort serialPort = SerialPort.getCommPort("COM3"); // Replace with your COM port
        serialAdapter = new SerialAdapter(serialPort, 9600); // Replace with your baud rate

        post("/packet", (request, response) -> {
            String body = request.body();
            Packet packet = gson.fromJson(body, Packet.class);

            // Send the packet to the Arduino
            boolean success = serialAdapter.sendPacket(packet);

            if (success) {
                response.status(200);
                return "Packet received and sent to Arduino.";
            } else {
                response.status(500);
                return "Failed to send packet to Arduino.";
            }
        });

        // Gracefully stop the server and close the serial port on shutdown
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            stop();
            if (serialAdapter != null) {
                serialAdapter.finish();
            }
        }));
    }
}