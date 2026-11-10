package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.json.JSONObject;
import org.junit.Test;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class MessageCodecTest {
    private static byte[] encode(Message message) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        MessageCodec.write(out, message);
        return out.toByteArray();
    }

    private static byte[] frame(int headerLength, int payloadLength, byte[] body) {
        byte[] data = new byte[8 + body.length];
        data[0] = (byte) (headerLength >>> 24);
        data[1] = (byte) (headerLength >>> 16);
        data[2] = (byte) (headerLength >>> 8);
        data[3] = (byte) headerLength;
        data[4] = (byte) (payloadLength >>> 24);
        data[5] = (byte) (payloadLength >>> 16);
        data[6] = (byte) (payloadLength >>> 8);
        data[7] = (byte) payloadLength;
        System.arraycopy(body, 0, data, 8, body.length);
        return data;
    }

    @Test
    public void roundTripWithPayload() throws Exception {
        JSONObject header = new JSONObject().put("id", 7).put("cmd", "frame").put("名字", "三月七");
        byte[] payload = {0, 1, 2, (byte) 0xFF, (byte) 0x80};
        byte[] wire = encode(new Message(header, payload));

        Message decoded = MessageCodec.read(new ByteArrayInputStream(wire), 1024, 1024);
        assertEquals(7, decoded.header.getInt("id"));
        assertEquals("frame", decoded.header.getString("cmd"));
        assertEquals("三月七", decoded.header.getString("名字"));
        assertArrayEquals(payload, decoded.payload);
    }

    @Test
    public void wireLayoutIsTwoBigEndianLengthsThenHeaderThenPayload() throws Exception {
        byte[] wire = encode(new Message(new JSONObject().put("a", 1), new byte[] {9, 8, 7}));
        byte[] json = "{\"a\":1}".getBytes(StandardCharsets.UTF_8);
        assertEquals(8 + json.length + 3, wire.length);
        assertArrayEquals(new byte[] {0, 0, 0, (byte) json.length, 0, 0, 0, 3}, java.util.Arrays.copyOf(wire, 8));
        assertArrayEquals(json, java.util.Arrays.copyOfRange(wire, 8, 8 + json.length));
        assertArrayEquals(new byte[] {9, 8, 7}, java.util.Arrays.copyOfRange(wire, 8 + json.length, wire.length));
    }

    @Test
    public void writesOnlyTheGivenPayloadSlice() throws Exception {
        byte[] backing = {1, 2, 3, 4, 5, 6};
        byte[] wire = encode(new Message(new JSONObject().put("a", 1), backing, 2, 3));
        Message decoded = MessageCodec.read(new ByteArrayInputStream(wire), 1024, 1024);
        assertArrayEquals(new byte[] {3, 4, 5}, decoded.payload);
    }

    @Test
    public void readsConsecutiveMessagesAndReturnsNullAtCleanEnd() throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        MessageCodec.write(out, new Message(new JSONObject().put("n", 1)));
        MessageCodec.write(out, new Message(new JSONObject().put("n", 2), new byte[] {5}));
        ByteArrayInputStream in = new ByteArrayInputStream(out.toByteArray());

        assertEquals(1, MessageCodec.read(in, 1024, 1024).header.getInt("n"));
        Message second = MessageCodec.read(in, 1024, 1024);
        assertEquals(2, second.header.getInt("n"));
        assertEquals(1, second.payloadLength);
        assertNull(MessageCodec.read(in, 1024, 1024));
    }

    @Test
    public void truncatedFrameIsAnError() throws Exception {
        byte[] wire = encode(new Message(new JSONObject().put("a", 1), new byte[] {1, 2, 3}));
        for (int cut = 1; cut < wire.length; cut++) {
            try {
                MessageCodec.read(new ByteArrayInputStream(wire, 0, cut), 1024, 1024);
                fail("accepted a frame cut at " + cut);
            } catch (EOFException expected) {
                // 帧中途断开
            }
        }
    }

    @Test
    public void rejectsOversizedHeaderBeforeReadingIt() throws Exception {
        byte[] wire = frame(2000, 0, new byte[0]);
        try {
            MessageCodec.read(new ByteArrayInputStream(wire), 1024, 1024);
            fail();
        } catch (ProtocolException expected) {
            assertTrue(expected.getMessage().contains("header length"));
        }
    }

    @Test
    public void rejectsEmptyHeaderAndHugeLengths() throws Exception {
        for (byte[] wire : new byte[][] {
                frame(0, 0, new byte[0]),
                frame(-1, 0, new byte[0]),
                frame(2, -1, "{}".getBytes(StandardCharsets.UTF_8)),
        }) {
            try {
                MessageCodec.read(new ByteArrayInputStream(wire), 1024, 1024);
                fail();
            } catch (ProtocolException expected) {
                // 长度越界
            }
        }
    }

    @Test
    public void rejectsPayloadOverTheLimit() throws Exception {
        byte[] wire = encode(new Message(new JSONObject().put("a", 1), new byte[5]));
        try {
            MessageCodec.read(new ByteArrayInputStream(wire), 1024, 4);
            fail();
        } catch (ProtocolException expected) {
            assertTrue(expected.getMessage().contains("payload length"));
        }
        // 握手阶段不允许带负载
        try {
            MessageCodec.read(new ByteArrayInputStream(wire), Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0);
            fail();
        } catch (ProtocolException expected) {
            // 负载超限
        }
    }

    @Test
    public void rejectsHeaderThatIsNotAJsonObject() throws Exception {
        for (String text : new String[] {"[1,2]", "hello", "{\"a\":"}) {
            byte[] body = text.getBytes(StandardCharsets.UTF_8);
            try {
                MessageCodec.read(new ByteArrayInputStream(frame(body.length, 0, body)), 1024, 1024);
                fail("accepted " + text);
            } catch (ProtocolException expected) {
                // 头不是 JSON 对象
            }
        }
    }

    @Test
    public void okAndErrorResponsesCarryTheRequestId() throws Exception {
        JSONObject request = new JSONObject().put("id", 42).put("cmd", "tap");
        JSONObject ok = Message.ok(request);
        assertEquals(42, ok.getInt("id"));
        assertTrue(ok.getBoolean("ok"));

        JSONObject error = Message.error(request, Protocol.E_TIMEOUT, "too slow");
        assertEquals(42, error.getInt("id"));
        assertFalse(error.getBoolean("ok"));
        assertEquals("timeout", error.getJSONObject("error").getString("code"));
        assertEquals("too slow", error.getJSONObject("error").getString("message"));

        assertFalse(Message.error(new JSONObject(), Protocol.E_BAD_REQUEST, null).has("id"));
    }
}
