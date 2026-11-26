package org.march7th.deviceservice.core;

import java.nio.ByteBuffer;

/** 低频复核已采集的 RGBA 帧；不另开截图，也不逐帧计算。 */
final class BlackFrame {
    static boolean isBlack(ByteBuffer buffer, int rowStride, int width, int height) {
        if (width <= 0 || height <= 0 || rowStride < (long) width * 4
                || (long) (height - 1) * rowStride + (long) width * 4 > buffer.capacity()) {
            throw new IllegalArgumentException("invalid RGBA frame dimensions");
        }
        ByteBuffer pixels = buffer.duplicate();
        pixels.clear();
        int tw = Math.min(80, width);
        int th = Math.min(45, height);
        int count = tw * th;
        long luma = 0;
        int nonblack = 0;
        for (int y = 0; y < th; y++) {
            int row = ((2 * y + 1) * height / (2 * th)) * rowStride;
            for (int x = 0; x < tw; x++) {
                int pos = row + (2 * x + 1) * width / (2 * tw) * 4;
                int r = pixels.get(pos) & 255;
                int g = pixels.get(pos + 1) & 255;
                int b = pixels.get(pos + 2) & 255;
                int peak = Math.max(r, Math.max(g, b));
                if (peak > 16) return false;
                if (peak > 8) nonblack++;
                luma += (299 * r + 587 * g + 114 * b + 500) / 1000;
            }
        }
        if (luma > (long) count * 3 || nonblack * 1000 > count) return false;
        // 和 Python 启动检测一样保护细小的加载文字、光标和进度点，忽略 alpha 与行填充。
        byte[] row = new byte[width * 4];
        for (int y = 0; y < height; y++) {
            pixels.position(y * rowStride);
            pixels.get(row);
            for (int x = 0; x < row.length; x += 4) {
                if ((row[x] & 255) > 16 || (row[x + 1] & 255) > 16 || (row[x + 2] & 255) > 16) return false;
            }
        }
        return true;
    }
}
