package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertSame;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

import java.nio.ByteBuffer;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.zip.Inflater;

public class FrameEncoderTest {
    private static final int WIDTH = 7;
    private static final int HEIGHT = 5;
    /** 每行比 width * 4 多出 12 个字节的填充。 */
    private static final int STRIDE = WIDTH * 4 + 12;

    /** 像素 (x, y) 的 RGBA 是 (x, y, x + y, 255)，行填充全是 0xEE。最后一行没有填充。 */
    private static ByteBuffer paddedSource() {
        ByteBuffer buffer = ByteBuffer.allocateDirect(STRIDE * (HEIGHT - 1) + WIDTH * 4);
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                buffer.put((byte) x).put((byte) y).put((byte) (x + y)).put((byte) 255);
            }
            if (y < HEIGHT - 1) {
                for (int i = 0; i < 12; i++) {
                    buffer.put((byte) 0xEE);
                }
            }
        }
        buffer.position(3).limit(10); // 调用方留下的 position/limit 不应该影响结果
        return buffer;
    }

    @Test
    public void copiesFullFrameWithoutRowPadding() {
        byte[] out = new byte[WIDTH * HEIGHT * 4];
        FrameEncoder.copyRegion(paddedSource(), STRIDE, 0, 0, WIDTH, HEIGHT, 4, out);
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                int i = (y * WIDTH + x) * 4;
                assertEquals(x, out[i]);
                assertEquals(y, out[i + 1]);
                assertEquals(x + y, out[i + 2]);
                assertEquals((byte) 255, out[i + 3]);
            }
        }
    }

    @Test
    public void dropsAlphaForRgb() {
        byte[] out = new byte[WIDTH * HEIGHT * 3];
        FrameEncoder.copyRegion(paddedSource(), STRIDE, 0, 0, WIDTH, HEIGHT, 3, out);
        for (int y = 0; y < HEIGHT; y++) {
            for (int x = 0; x < WIDTH; x++) {
                int i = (y * WIDTH + x) * 3;
                assertEquals(x, out[i]);
                assertEquals(y, out[i + 1]);
                assertEquals(x + y, out[i + 2]);
            }
        }
    }

    @Test
    public void cropsARegion() {
        byte[] out = new byte[3 * 2 * 3];
        FrameEncoder.copyRegion(paddedSource(), STRIDE, 2, 3, 3, 2, 3, out);
        assertArrayEquals(new byte[] {
                2, 3, 5, 3, 3, 6, 4, 3, 7,
                2, 4, 6, 3, 4, 7, 4, 4, 8,
        }, out);
    }

    @Test
    public void doesNotDisturbTheSourceBuffer() {
        ByteBuffer source = paddedSource();
        FrameEncoder.copyRegion(source, STRIDE, 0, 0, WIDTH, HEIGHT, 4, new byte[WIDTH * HEIGHT * 4]);
        assertEquals(3, source.position());
        assertEquals(10, source.limit());
    }

    @Test
    public void rejectsRegionsOutsideTheBuffer() {
        byte[] out = new byte[WIDTH * HEIGHT * 4];
        int[][] bad = {
                {-1, 0, 2, 2}, {0, -1, 2, 2}, {0, 0, 0, 2}, {0, 0, 2, 0},
                {WIDTH + 2, 0, 2, 2},          // 超出一行的字节数
                {0, HEIGHT - 1, 2, 2},         // 超出下边
        };
        for (int[] region : bad) {
            try {
                FrameEncoder.copyRegion(paddedSource(), STRIDE, region[0], region[1], region[2], region[3], 4, out);
                fail("accepted " + java.util.Arrays.toString(region));
            } catch (IllegalArgumentException expected) {
                // 区域越界
            }
        }
        try {
            FrameEncoder.copyRegion(paddedSource(), STRIDE, 0, 0, WIDTH, HEIGHT, 4, new byte[10]);
            fail();
        } catch (IllegalArgumentException expected) {
            // 输出缓冲太小
        }
    }

    private static byte[] randomPixels(int width, int height, int channels) {
        byte[] pixels = new byte[width * height * channels];
        new Random(7).nextBytes(pixels);
        // 一半做成平滑内容，让压缩和预测有东西可做
        for (int i = 0; i < pixels.length / 2; i++) {
            pixels[i] = (byte) (i / 9);
        }
        return pixels;
    }

    /** 测试里的参考解码：逐条解压，拼起来，再按预测方向累加。 */
    private static byte[] decode(FrameEncoder.Encoded encoded, int width, int height, int channels, String predictor)
            throws Exception {
        byte[] out = new byte[width * height * channels];
        int inOffset = 0;
        int outOffset = 0;
        for (int i = 0; i < encoded.chunkLengths.length; i++) {
            Inflater inflater = new Inflater();
            inflater.setInput(encoded.data, inOffset, encoded.chunkLengths[i]);
            int expected = encoded.chunkRows[i] * width * channels;
            int done = 0;
            while (done < expected) {
                int n = inflater.inflate(out, outOffset + done, expected - done);
                assertTrue("zlib stream ended early", n > 0);
                done += n;
            }
            assertTrue(inflater.finished() || inflater.inflate(new byte[1]) == 0);
            inflater.end();
            inOffset += encoded.chunkLengths[i];
            outOffset += expected;
        }
        assertEquals(encoded.length, inOffset);
        assertEquals(out.length, outOffset);
        int rowBytes = width * channels;
        if (FrameEncoder.PREDICTOR_LEFT.equals(predictor)) {
            for (int row = 0; row < height; row++) {
                for (int i = row * rowBytes + channels; i < (row + 1) * rowBytes; i++) {
                    out[i] = (byte) (out[i] + out[i - channels]);
                }
            }
        } else if (FrameEncoder.PREDICTOR_UP.equals(predictor)) {
            for (int i = rowBytes; i < out.length; i++) {
                out[i] = (byte) (out[i] + out[i - rowBytes]);
            }
        }
        return out;
    }

    @Test
    public void rawEncodingsReturnTheSameBuffer() throws Exception {
        byte[] pixels = randomPixels(8, 4, 4);
        FrameEncoder.Options options = new FrameEncoder.Options();
        options.encoding = FrameEncoder.RGBA;
        FrameEncoder.Encoded encoded = FrameEncoder.encode(pixels, 8, 4, options, null);
        assertSame(pixels, encoded.data);
        assertEquals(8 * 4 * 4, encoded.length);
        assertNull(encoded.chunkLengths);
    }

    @Test
    public void compressedEncodingsAreLossless() throws Exception {
        int width = 33;
        int height = 21;
        ExecutorService pool = Executors.newFixedThreadPool(3);
        try {
            for (String encoding : new String[] {FrameEncoder.RGB_ZLIB, FrameEncoder.RGBA_ZLIB}) {
                for (String predictor : new String[] {"none", "left", "up"}) {
                    for (int chunks : new int[] {1, 2, 4, 16}) {
                        FrameEncoder.Options options = new FrameEncoder.Options();
                        options.encoding = encoding;
                        options.predictor = predictor;
                        options.chunks = chunks;
                        options.validate();
                        int channels = options.channels();
                        byte[] original = randomPixels(width, height, channels);
                        FrameEncoder.Encoded encoded = FrameEncoder.encode(original.clone(), width, height, options,
                                chunks > 1 ? pool : null);
                        String label = encoding + "/" + predictor + "/" + chunks;
                        assertEquals(label, chunks, encoded.chunkLengths.length);
                        int rows = 0;
                        for (int value : encoded.chunkRows) {
                            rows += value;
                        }
                        assertEquals(label, height, rows);
                        assertArrayEquals(label, original, decode(encoded, width, height, channels, predictor));
                    }
                }
            }
        } finally {
            pool.shutdownNow();
        }
    }

    @Test
    public void neverMoreChunksThanRows() throws Exception {
        FrameEncoder.Options options = new FrameEncoder.Options();
        options.encoding = FrameEncoder.RGB_ZLIB;
        options.chunks = 8;
        byte[] original = randomPixels(10, 3, 3);
        FrameEncoder.Encoded encoded = FrameEncoder.encode(original.clone(), 10, 3, options, null);
        assertEquals(3, encoded.chunkLengths.length);
        assertArrayEquals(original, decode(encoded, 10, 3, 3, "none"));
    }

    @Test
    public void incompressibleDataStillFits() throws Exception {
        byte[] noise = new byte[64 * 64 * 3];
        new Random(1).nextBytes(noise);
        FrameEncoder.Options options = new FrameEncoder.Options();
        options.encoding = FrameEncoder.RGB_ZLIB;
        FrameEncoder.Encoded encoded = FrameEncoder.encode(noise.clone(), 64, 64, options, null);
        assertTrue(encoded.length > noise.length);
        assertArrayEquals(noise, decode(encoded, 64, 64, 3, "none"));
    }

    @Test
    public void optionsValidation() {
        String[][] bad = {{"png", "none"}, {"rgb-zlib", "paeth"}};
        for (String[] pair : bad) {
            FrameEncoder.Options options = new FrameEncoder.Options();
            options.encoding = pair[0];
            options.predictor = pair[1];
            try {
                options.validate();
                fail();
            } catch (IllegalArgumentException expected) {
                // 参数不认识
            }
        }
        for (int[] pair : new int[][] {{0, 1}, {10, 1}, {1, 0}, {1, 17}}) {
            FrameEncoder.Options options = new FrameEncoder.Options();
            options.level = pair[0];
            options.chunks = pair[1];
            try {
                options.validate();
                fail();
            } catch (IllegalArgumentException expected) {
                // 数值越界
            }
        }
    }

    @Test
    public void cacheKeyIgnoresCompressionKnobsForRawEncodings() {
        FrameEncoder.Options a = new FrameEncoder.Options();
        FrameEncoder.Options b = new FrameEncoder.Options();
        b.level = 9;
        b.chunks = 4;
        assertEquals(a.cacheKey(), b.cacheKey());
        a.encoding = FrameEncoder.RGB_ZLIB;
        b.encoding = FrameEncoder.RGB_ZLIB;
        assertTrue(!a.cacheKey().equals(b.cacheKey()));
    }
}
