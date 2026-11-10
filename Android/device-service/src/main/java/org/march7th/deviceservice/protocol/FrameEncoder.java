package org.march7th.deviceservice.protocol;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.zip.Deflater;

/**
 * 帧的裁剪与编码，全部无损。只依赖 java.*，可以脱离设备测试。
 *
 * 输出的像素按行紧密排列，没有行填充，行序自上而下。
 */
public final class FrameEncoder {
    public static final String RGBA = "rgba";
    public static final String RGB = "rgb";
    public static final String RGB_ZLIB = "rgb-zlib";
    public static final String RGBA_ZLIB = "rgba-zlib";

    public static final String PREDICTOR_NONE = "none";
    public static final String PREDICTOR_LEFT = "left";
    public static final String PREDICTOR_UP = "up";

    /** 编码参数。 */
    public static final class Options {
        public String encoding = RGB;
        /** zlib 压缩级别，1 最快。 */
        public int level = 1;
        /** 压缩前的预测：none、left（减去左边的像素）、up（减去上一行的像素）。 */
        public String predictor = PREDICTOR_NONE;
        /** 把画面横向切成几条分别压缩，每条是独立的 zlib 流。 */
        public int chunks = 1;

        public boolean compressed() {
            return RGB_ZLIB.equals(encoding) || RGBA_ZLIB.equals(encoding);
        }

        public int channels() {
            return RGB.equals(encoding) || RGB_ZLIB.equals(encoding) ? 3 : 4;
        }

        public void validate() {
            if (!RGBA.equals(encoding) && !RGB.equals(encoding) && !RGB_ZLIB.equals(encoding) && !RGBA_ZLIB.equals(encoding)) {
                throw new IllegalArgumentException("unknown encoding: " + encoding);
            }
            if (level < 1 || level > 9) {
                throw new IllegalArgumentException("level must be 1..9");
            }
            if (!PREDICTOR_NONE.equals(predictor) && !PREDICTOR_LEFT.equals(predictor) && !PREDICTOR_UP.equals(predictor)) {
                throw new IllegalArgumentException("unknown predictor: " + predictor);
            }
            if (chunks < 1 || chunks > 16) {
                throw new IllegalArgumentException("chunks must be 1..16");
            }
        }

        /** 两次请求的参数相同时可以复用上一次的编码结果。 */
        public String cacheKey() {
            return compressed() ? encoding + '/' + level + '/' + predictor + '/' + chunks : encoding;
        }
    }

    /** 编码结果。compressed 为 false 时 chunkLengths 为 null。 */
    public static final class Encoded {
        public final byte[] data;
        public final int length;
        /** 每条 zlib 流的字节数，按顺序拼成 data。 */
        public final int[] chunkLengths;
        /** 每条 zlib 流覆盖的行数。 */
        public final int[] chunkRows;

        Encoded(byte[] data, int length, int[] chunkLengths, int[] chunkRows) {
            this.data = data;
            this.length = length;
            this.chunkLengths = chunkLengths;
            this.chunkRows = chunkRows;
        }
    }

    private FrameEncoder() {
    }

    /**
     * 从带行填充的 RGBA 缓冲里拷出一块区域。
     *
     * @param source    ImageReader 的像素缓冲，position 和 limit 不会被改动
     * @param rowStride 每行占用的字节数，可能大于 width * 4
     * @param channels  输出通道数：4 保留 RGBA，3 丢掉 alpha
     * @param out       长度至少为 width * height * channels
     */
    public static void copyRegion(ByteBuffer source, int rowStride, int x, int y, int width, int height, int channels, byte[] out) {
        if (channels != 3 && channels != 4) {
            throw new IllegalArgumentException("channels must be 3 or 4");
        }
        if (x < 0 || y < 0 || width <= 0 || height <= 0 || rowStride < (x + width) * 4) {
            throw new IllegalArgumentException("region does not fit the row stride");
        }
        if (out.length < (long) width * height * channels) {
            throw new IllegalArgumentException("output buffer too small");
        }
        ByteBuffer view = source.duplicate();
        view.clear();
        // 最后一行可以没有行填充，所以只要求到最后一个像素为止。
        long needed = (long) (y + height - 1) * rowStride + (long) (x + width) * 4;
        if (view.capacity() < needed) {
            throw new IllegalArgumentException("region exceeds the source buffer");
        }
        int rowBytes = width * 4;
        if (channels == 4) {
            for (int row = 0; row < height; row++) {
                view.position((y + row) * rowStride + x * 4);
                view.get(out, row * rowBytes, rowBytes);
            }
            return;
        }
        byte[] line = new byte[rowBytes];
        int o = 0;
        for (int row = 0; row < height; row++) {
            view.position((y + row) * rowStride + x * 4);
            view.get(line, 0, rowBytes);
            for (int i = 0; i < rowBytes; i += 4) {
                out[o] = line[i];
                out[o + 1] = line[i + 1];
                out[o + 2] = line[i + 2];
                o += 3;
            }
        }
    }

    /** 就地做预测。解码方按相反方向累加即可还原（对 256 取模）。 */
    public static void applyPredictor(byte[] data, int width, int height, int channels, String predictor) {
        int rowBytes = width * channels;
        if (PREDICTOR_LEFT.equals(predictor)) {
            for (int row = 0; row < height; row++) {
                int start = row * rowBytes;
                for (int i = start + rowBytes - 1; i >= start + channels; i--) {
                    data[i] = (byte) (data[i] - data[i - channels]);
                }
            }
        } else if (PREDICTOR_UP.equals(predictor)) {
            for (int i = rowBytes * height - 1; i >= rowBytes; i--) {
                data[i] = (byte) (data[i] - data[i - rowBytes]);
            }
        }
    }

    /**
     * 按 options 编码一块已经紧密排列的像素。
     *
     * @param pixels 长度至少为 width * height * options.channels()，压缩时内容会被预测步骤改写
     * @param pool   chunks 大于 1 时用来并行压缩；为 null 时串行
     */
    public static Encoded encode(byte[] pixels, int width, int height, Options options, ExecutorService pool)
            throws InterruptedException {
        int channels = options.channels();
        int rowBytes = width * channels;
        int total = rowBytes * height;
        if (!options.compressed()) {
            return new Encoded(pixels, total, null, null);
        }
        applyPredictor(pixels, width, height, channels, options.predictor);
        int chunks = Math.min(options.chunks, height);
        int[] rows = new int[chunks];
        for (int i = 0; i < chunks; i++) {
            rows[i] = height / chunks + (i < height % chunks ? 1 : 0);
        }
        byte[][] outputs = new byte[chunks][];
        int[] lengths = new int[chunks];
        if (chunks == 1 || pool == null) {
            int offset = 0;
            for (int i = 0; i < chunks; i++) {
                int length = rows[i] * rowBytes;
                outputs[i] = new byte[deflateBound(length)];
                lengths[i] = deflate(pixels, offset, length, options.level, outputs[i]);
                offset += length;
            }
        } else {
            List<Future<Integer>> futures = new ArrayList<>(chunks);
            int offset = 0;
            for (int i = 0; i < chunks; i++) {
                final int from = offset;
                final int length = rows[i] * rowBytes;
                final byte[] target = new byte[deflateBound(length)];
                outputs[i] = target;
                futures.add(pool.submit(() -> deflate(pixels, from, length, options.level, target)));
                offset += length;
            }
            for (int i = 0; i < chunks; i++) {
                try {
                    lengths[i] = futures.get(i).get();
                } catch (ExecutionException e) {
                    throw new IllegalStateException("compression failed", e.getCause());
                }
            }
        }
        if (chunks == 1) {
            return new Encoded(outputs[0], lengths[0], lengths, rows);
        }
        int size = 0;
        for (int length : lengths) {
            size += length;
        }
        byte[] joined = new byte[size];
        int position = 0;
        for (int i = 0; i < chunks; i++) {
            System.arraycopy(outputs[i], 0, joined, position, lengths[i]);
            position += lengths[i];
        }
        return new Encoded(joined, size, lengths, rows);
    }

    /** zlib 在最坏情况下的输出上限（不可压缩数据会略微膨胀）。 */
    static int deflateBound(int length) {
        return length + (length >> 12) + (length >> 14) + (length >> 25) + 64;
    }

    private static int deflate(byte[] input, int offset, int length, int level, byte[] output) {
        Deflater deflater = new Deflater(level);
        try {
            deflater.setInput(input, offset, length);
            deflater.finish();
            int written = 0;
            while (!deflater.finished()) {
                if (written == output.length) {
                    throw new IllegalStateException("deflate output exceeded its bound");
                }
                written += deflater.deflate(output, written, output.length - written);
            }
            return written;
        } finally {
            deflater.end();
        }
    }
}
