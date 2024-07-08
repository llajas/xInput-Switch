package com.example;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public class SerialAdapter {
    private final OutputStream outputStream;
    private final InputStream inputStream;

    public SerialAdapter(OutputStream outputStream, InputStream inputStream) {
        this.outputStream = outputStream;
        this.inputStream = inputStream;
    }

    public void write(byte[] data) throws IOException {
        outputStream.write(data);
        outputStream.flush();
    }

    public int read(byte[] buffer) throws IOException {
        return inputStream.read(buffer);
    }
}
