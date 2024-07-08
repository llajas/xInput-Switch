package com.example;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public final class SerialAdapter {

    private final OutputStream outputStream;
    private final InputStream inputStream;

    public SerialAdapter(final OutputStream outputStream, final InputStream inputStream) {
        this.outputStream = outputStream;
        this.inputStream = inputStream;
    }

    public boolean sendPacket(final byte[] packet) {
        try {
            outputStream.write(packet);
            outputStream.flush();
            return true;
        } catch (IOException e) {
            e.printStackTrace();
            return false;
        }
    }

    public byte[] receivePacket() {
        final byte[] buffer = new byte[1024];
        try {
            final int readBytes = inputStream.read(buffer);
            if (readBytes > 0) {
                return buffer;
            } else {
                throw new IOException("Incomplete packet received");
            }
        } catch (IOException e) {
            e.printStackTrace();
            return null;
        }
    }

    public void close() {
        try {
            outputStream.close();
            inputStream.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
