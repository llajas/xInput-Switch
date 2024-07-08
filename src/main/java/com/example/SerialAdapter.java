package com.example;

import com.fazecast.jSerialComm.SerialPort;
import com.example.util.Crc;
import java.io.IOException;
import java.util.Arrays;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.apache.commons.lang3.SystemUtils;

public class SerialAdapter {
    private static final Logger logger = Logger.getLogger(SerialAdapter.class.getName());
    private final SerialPort serialPort;
    private static final byte COMMAND_SYNC_1 = 0x33;
    private static final byte COMMAND_SYNC_2 = (byte) 0xCC;
    private static final byte COMMAND_SYNC_START = (byte) 0xFF;
    private static final byte RESP_SYNC_START = (byte) 0xFF;
    private static final byte RESP_SYNC_1 = (byte) 0xCC;
    private static final byte RESP_SYNC_OK = 0x33;
    private static final int WRITE_TIMEOUT = 0; // Blocking write
    private static final int READ_TIMEOUT = 18; // Default buffer delay in Windows is 16ms
    private boolean isBaudrateInvalid = false;
    private Status status = Status.OUT_OF_SYNC;

    private enum Status {
        OUT_OF_SYNC,
        SYNCED,
        SYNCING
    }

    public SerialAdapter(SerialPort serialPort, int baudrate) {
        this.serialPort = serialPort;
        if (serialPort != null) {
            serialPort.setNumDataBits(8);
            serialPort.setParity(SerialPort.NO_PARITY);
            serialPort.setNumStopBits(SerialPort.ONE_STOP_BIT);
            serialPort.setFlowControl(SerialPort.FLOW_CONTROL_DISABLED);
            serialPort.setComPortTimeouts(SerialPort.TIMEOUT_WRITE_BLOCKING | SerialPort.TIMEOUT_READ_BLOCKING, READ_TIMEOUT, WRITE_TIMEOUT);
            if (SystemUtils.IS_OS_WINDOWS) {
                serialPort.allowElevatedPermissionsRequest();
            }
            serialPort.openPort();
            if (!serialPort.setBaudRate(baudrate)) {
                this.isBaudrateInvalid = true;
            }
        }
    }

    public boolean isBaudrateInvalid() {
        return isBaudrateInvalid;
    }

    public synchronized void write(byte[] data) throws IOException {
        if (serialPort != null && serialPort.isOpen()) {
            byte[] dataWithCrc = Arrays.copyOf(data, data.length + 1);
            dataWithCrc[data.length] = Crc.fromBytes(data);
            serialPort.writeBytes(dataWithCrc, dataWithCrc.length);
            logger.fine("Writing to serial: " + byteArrayToHex(dataWithCrc)); // Change log level to FINE
        }
    }

    public synchronized int read(byte[] buffer) throws IOException {
        if (serialPort != null && serialPort.isOpen()) {
            int bytesRead = serialPort.readBytes(buffer, buffer.length);
            logger.fine("Read from serial: " + byteArrayToHex(buffer, bytesRead)); // Change log level to FINE
            return bytesRead;
        }
        return 0;
    }

    public synchronized void sync() throws IOException {
        if (serialPort == null) {
            status = Status.SYNCED;
            return;
        }
        final long t1 = System.currentTimeMillis();
        if (status == Status.SYNCING) {
            return;
        }
        if (status == Status.SYNCED) {
            return;
        }
        status = Status.SYNCING;

        final byte b = COMMAND_SYNC_START;
        final byte[] bufferFlushBytes = {b, b, b, b, b, b, b, b, b};
        serialPort.writeBytes(bufferFlushBytes, bufferFlushBytes.length);
        logger.fine("Bytes written for sync"); // Change log level to FINE

        long timestamp = System.currentTimeMillis();
        int available = 0;
        while (System.currentTimeMillis() - timestamp < READ_TIMEOUT) {
            final int now = serialPort.bytesAvailable();
            if (now > available) {
                available = now;
                timestamp = System.currentTimeMillis();
            }
        }
        if (available >= 1 && available <= 9) {
            final byte[] rx = new byte[available];
            serialPort.readBytes(rx, available);
            logger.fine("Received " + available + " bytes: " + byteArrayToHex(rx, available)); // Change log level to FINE
            if (rx[available - 1] == RESP_SYNC_START) {
                logger.fine("RESP_SYNC_START received as last byte"); // Change log level to FINE
                sendByte(COMMAND_SYNC_1);
                logger.fine("Sending COMMAND_SYNC_1"); // Change log level to FINE
                byte response = readByte();
                logger.fine("Response: " + response); // Change log level to FINE
                if (response == RESP_SYNC_1) {
                    logger.fine("RESP_SYNC_1 received"); // Change log level to FINE
                    sendByte(COMMAND_SYNC_2);
                    logger.fine("Sending COMMAND_SYNC_2"); // Change log level to FINE
                    response = readByte();
                    logger.fine("Response: " + response); // Change log level to FINE
                    if (response == RESP_SYNC_OK) {
                        logger.fine("RESP_SYNC_OK received"); // Change log level to FINE
                        status = Status.SYNCED;
                        logger.info("Synchronization took " + (System.currentTimeMillis() - t1) + " ms");
                        return;
                    }
                }
            }
        }

        status = Status.OUT_OF_SYNC;
        logger.severe("Couldn't sync");
        throw new IOException("Couldn't sync with the MCU");
    }

    private synchronized void sendByte(final byte b) {
        if (serialPort != null) {
            byte[] txByteBuffer = new byte[]{b};
            serialPort.writeBytes(txByteBuffer, 1);
        }
    }

    private synchronized byte readByte() {
        byte[] rxByteBuffer = new byte[1];
        if (serialPort != null) {
            serialPort.readBytes(rxByteBuffer, 1);
        }
        return rxByteBuffer[0];
    }

    public void close() {
        if (serialPort != null && serialPort.isOpen()) {
            serialPort.closePort();
            logger.info("Serial port closed.");
        }
    }

    public static String byteArrayToHex(byte[] byteArray) {
        StringBuilder sb = new StringBuilder();
        for (byte b : byteArray) {
            sb.append(String.format("%02X ", b));
        }
        return sb.toString();
    }

    public static String byteArrayToHex(byte[] byteArray, int length) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < length; i++) {
            sb.append(String.format("%02X ", byteArray[i]));
        }
        return sb.toString();
    }
}
