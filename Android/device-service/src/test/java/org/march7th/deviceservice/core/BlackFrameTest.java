package org.march7th.deviceservice.core;

import org.junit.Test;
import java.nio.ByteBuffer;
import static org.junit.Assert.*;

public class BlackFrameTest {
    @Test
    public void ignoresAlphaAndRowPaddingAndPreservesTheBufferView() {
        int width = 1280, height = 720, stride = width * 4 + 16;
        ByteBuffer pixels = ByteBuffer.allocate(stride * height);
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int p = y * stride + x * 4;
                pixels.put(p, (byte) 2).put(p + 1, (byte) 2).put(p + 2, (byte) 2).put(p + 3, (byte) 255);
            }
            for (int x = width * 4; x < stride; x++) pixels.put(y * stride + x, (byte) 255);
        }
        pixels.position(7).limit(21);
        assertTrue(BlackFrame.isBlack(pixels, stride, width, height));
        assertEquals(7, pixels.position());
        assertEquals(21, pixels.limit());
    }

    @Test
    public void aTinyUnsampledLoadingPixelPreventsAnUnnecessaryTouch() {
        ByteBuffer pixels = ByteBuffer.allocate(1280 * 720 * 4);
        pixels.put(4, (byte) 255); // 80x45 缩略图没有采到这个像素。
        assertFalse(BlackFrame.isBlack(pixels, 1280 * 4, 1280, 720));
    }

    @Test
    public void distinguishesNearBlackFromVisibleDarkContent() {
        for (int value : new int[]{0, 3, 8, 32, 255}) {
            ByteBuffer pixels = ByteBuffer.allocate(80 * 45 * 4);
            for (int p = 0; p < pixels.capacity(); p += 4) {
                pixels.put(p, (byte) value).put(p + 1, (byte) value).put(p + 2, (byte) value);
            }
            assertEquals(value <= 3, BlackFrame.isBlack(pixels, 80 * 4, 80, 45));
        }
        assertThrows(IllegalArgumentException.class, () -> BlackFrame.isBlack(ByteBuffer.allocate(16), 4, 2, 2));
        assertThrows(IllegalArgumentException.class, () -> BlackFrame.isBlack(ByteBuffer.allocate(16), 12, 3, 2));
    }
}
