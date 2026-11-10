package org.march7th.deviceservice.protocol;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.EOFException;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * 长度前缀帧的编解码。
 *
 * <pre>
 * uint32 BE  头长度 H（1..maxHeader）
 * uint32 BE  负载长度 P（0..maxPayload）
 * H 字节     UTF-8 JSON 对象
 * P 字节     二进制负载
 * </pre>
 */
public final class MessageCodec {
    private MessageCodec() {
    }

    /**
     * 读一条消息。
     *
     * @return 对端在帧边界正常关闭时返回 null
     */
    public static Message read(InputStream in, int maxHeader, int maxPayload) throws IOException {
        byte[] prefix = new byte[8];
        int first = in.read(prefix, 0, 8);
        if (first < 0) {
            return null;
        }
        readFully(in, prefix, first, 8 - first);
        long headerLength = readUint32(prefix, 0);
        long payloadLength = readUint32(prefix, 4);
        if (headerLength < 1 || headerLength > maxHeader) {
            throw new ProtocolException("header length out of range: " + headerLength);
        }
        if (payloadLength > maxPayload) {
            throw new ProtocolException("payload length out of range: " + payloadLength);
        }
        byte[] headerBytes = new byte[(int) headerLength];
        readFully(in, headerBytes, 0, headerBytes.length);
        byte[] payload = new byte[(int) payloadLength];
        readFully(in, payload, 0, payload.length);
        JSONObject header;
        try {
            header = new JSONObject(new String(headerBytes, StandardCharsets.UTF_8));
        } catch (JSONException e) {
            throw new ProtocolException("header is not a JSON object", e);
        }
        return new Message(header, payload);
    }

    public static void write(OutputStream out, Message message) throws IOException {
        byte[] headerBytes = message.header.toString().getBytes(StandardCharsets.UTF_8);
        byte[] head = new byte[8 + headerBytes.length];
        writeUint32(head, 0, headerBytes.length);
        writeUint32(head, 4, message.payloadLength);
        System.arraycopy(headerBytes, 0, head, 8, headerBytes.length);
        out.write(head);
        if (message.payloadLength > 0) {
            out.write(message.payload, message.payloadOffset, message.payloadLength);
        }
        out.flush();
    }

    private static void readFully(InputStream in, byte[] buffer, int offset, int length) throws IOException {
        int done = 0;
        while (done < length) {
            int n = in.read(buffer, offset + done, length - done);
            if (n < 0) {
                throw new EOFException("connection closed inside a frame");
            }
            done += n;
        }
    }

    private static long readUint32(byte[] buffer, int offset) {
        return ((buffer[offset] & 0xFFL) << 24)
                | ((buffer[offset + 1] & 0xFFL) << 16)
                | ((buffer[offset + 2] & 0xFFL) << 8)
                | (buffer[offset + 3] & 0xFFL);
    }

    private static void writeUint32(byte[] buffer, int offset, int value) {
        buffer[offset] = (byte) (value >>> 24);
        buffer[offset + 1] = (byte) (value >>> 16);
        buffer[offset + 2] = (byte) (value >>> 8);
        buffer[offset + 3] = (byte) value;
    }
}
