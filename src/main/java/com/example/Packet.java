package com.example;

import java.util.function.Function;

public class Packet {

    private static final int PACKET_BUFFER_LENGTH = 8;
    private static final byte VENDORSPEC = 0x00;

    public static final Packet EMPTY_PACKET = new Packet(
            Buttons.noButtons(), Dpad.center(), Joystick.centered(), Joystick.centered());
    public static final byte[] EMPTY_PACKET_BUFFER = EMPTY_PACKET.getBuffer();

    private byte[] buffer;

    public Packet(Buttons buttons, Dpad dpad, Joystick leftJoystick, Joystick rightJoystick) {
        this.buffer = new byte[PACKET_BUFFER_LENGTH];

        // Buttons
        short buttonsValue = buttons.toShort();
        buffer[0] = (byte)(buttonsValue >> 8);
        buffer[1] = (byte)(buttonsValue);

        // DPAD
        buffer[2] = dpad.toByte();

        // Left joystick
        byte[] leftJoystickBytes = leftJoystick.toBytes();
        System.arraycopy(leftJoystickBytes, 0, buffer, 3, 2);

        // Right joystick
        byte[] rightJoystickBytes = rightJoystick.toBytes();
        System.arraycopy(rightJoystickBytes, 0, buffer, 5, 2);

        // Vendorspec
        buffer[7] = VENDORSPEC;
    }

    public byte[] getBuffer() {
        return buffer;
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("Packet{");
        sb.append("buttons=[");
        sb.append(String.format("%8s", Integer.toBinaryString(buffer[0] & 0xFF)).replace(' ', '0')).append(" ");
        sb.append(String.format("%8s", Integer.toBinaryString(buffer[1] & 0xFF)).replace(' ', '0')).append("], ");
        sb.append("dpad=").append(String.format("%8s", Integer.toBinaryString(buffer[2] & 0xFF)).replace(' ', '0')).append(", ");
        sb.append("leftJoystick=[").append(String.format("%8s", Integer.toBinaryString(buffer[3] & 0xFF)).replace(' ', '0')).append(", ");
        sb.append(String.format("%8s", Integer.toBinaryString(buffer[4] & 0xFF)).replace(' ', '0')).append("], ");
        sb.append("rightJoystick=[").append(String.format("%8s", Integer.toBinaryString(buffer[5] & 0xFF)).replace(' ', '0')).append(", ");
        sb.append(String.format("%8s", Integer.toBinaryString(buffer[6] & 0xFF)).replace(' ', '0')).append("], ");
        sb.append("vendorspec=").append(String.format("%8s", Integer.toBinaryString(buffer[7] & 0xFF)).replace(' ', '0'));
        sb.append('}');
        return sb.toString();
    }

    public static class Buttons {

        public enum Code {
            NONE, Y, B, A, X, L, R, ZL, ZR, MINUS, PLUS, LCLICK, RCLICK, HOME, CAPTURE;
        }

        private final boolean y, b, a, x, l, r, zl, zr, minus, plus, lclick, rclick, home, capture;

        public Buttons(Function<Code, Boolean> provider) {
            this.y = provider.apply(Code.Y);
            this.b = provider.apply(Code.B);
            this.a = provider.apply(Code.A);
            this.x = provider.apply(Code.X);
            this.l = provider.apply(Code.L);
            this.r = provider.apply(Code.R);
            this.zl = provider.apply(Code.ZL);
            this.zr = provider.apply(Code.ZR);
            this.minus = provider.apply(Code.MINUS);
            this.plus = provider.apply(Code.PLUS);
            this.lclick = provider.apply(Code.LCLICK);
            this.rclick = provider.apply(Code.RCLICK);
            this.home = provider.apply(Code.HOME);
            this.capture = provider.apply(Code.CAPTURE);
        }

        public short toShort() {
            int i = 0;
            i |= (y ? 1 : 0) << 0;
            i |= (b ? 1 : 0) << 1;
            i |= (a ? 1 : 0) << 2;
            i |= (x ? 1 : 0) << 3;
            i |= (l ? 1 : 0) << 4;
            i |= (r ? 1 : 0) << 5;
            i |= (zl ? 1 : 0) << 6;
            i |= (zr ? 1 : 0) << 7;
            i |= (minus ? 1 : 0) << 8;
            i |= (plus ? 1 : 0) << 9;
            i |= (lclick ? 1 : 0) << 10;
            i |= (rclick ? 1 : 0) << 11;
            i |= (home ? 1 : 0) << 12;
            i |= (capture ? 1 : 0) << 13;
            return (short) i;
        }

        public static Buttons noButtons() {
            return new Buttons(code -> false);
        }
    }

    public static class Dpad {

        private final boolean up, right, down, left;

        public Dpad(boolean up, boolean right, boolean down, boolean left) {
            this.up = up;
            this.right = right;
            this.down = down;
            this.left = left;
        }

        public byte toByte() {
            if (left) {
                if (up) {
                    return 0x07;
                } else if (down) {
                    return 0x05;
                } else {
                    return 0x06;
                }
            } else if (right) {
                if (up) {
                    return 0x01;
                } else if (down) {
                    return 0x03;
                } else {
                    return 0x02;
                }
            } else if (up) {
                return 0x00;
            } else if (down) {
                return 0x04;
            } else {
                return 0x08;
            }
        }

        public static Dpad center() {
            return new Dpad(false, false, false, false);
        }
    }

    public static class Joystick {

        private static final float MIN = -1.0f;
        private static final float MAX = 1.0f;
        private static final byte CENTER = (byte) 0x80;
        private static final int CENTER_INTEGER = 0x80;

        private final float x, y;

        public Joystick(float x, float y) {
            this.x = x;
            this.y = y;
        }

        public byte[] toBytes() {
            assert x >= MIN && x <= MAX;
            assert y >= MIN && y <= MAX;

            byte bx = (byte) ((x + 1.0) / 2.0 * 255);
            byte by = (byte) ((y + 1.0) / 2.0 * 255);

            if (Math.abs(bx - CENTER_INTEGER) < 10) {
                bx = CENTER;
            }
            if (Math.abs(by - CENTER_INTEGER) < 10) {
                by = CENTER;
            }

            return new byte[]{bx, by};
        }

        public static Joystick centered() {
            return new Joystick(0.0f, 0.0f);
        }
    }
}
