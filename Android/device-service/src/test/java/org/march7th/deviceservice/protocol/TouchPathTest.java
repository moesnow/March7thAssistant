package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.fail;

import org.junit.Test;

public class TouchPathTest {
    private static final float EPSILON = 1e-4f;

    @Test
    public void straightLineIsLinear() {
        TouchPath path = new TouchPath(new float[] {100, 300}, new float[] {50, 50});
        assertArrayEquals(new float[] {100, 50}, path.at(0), EPSILON);
        assertArrayEquals(new float[] {150, 50}, path.at(0.25), EPSILON);
        assertArrayEquals(new float[] {300, 50}, path.at(1), EPSILON);
    }

    @Test
    public void polylineAdvancesByDistanceNotBySegment() {
        // 第一段长 30，第二段长 10：走到一半时还在第一段上
        TouchPath path = new TouchPath(new float[] {0, 30, 30}, new float[] {0, 0, 10});
        assertArrayEquals(new float[] {20, 0}, path.at(0.5), EPSILON);
        assertArrayEquals(new float[] {30, 0}, path.at(0.75), EPSILON);
        assertArrayEquals(new float[] {30, 5}, path.at(0.875), EPSILON);
    }

    @Test
    public void outOfRangeFractionsClampToTheEnds() {
        TouchPath path = new TouchPath(new float[] {1, 9}, new float[] {2, 8});
        assertArrayEquals(new float[] {1, 2}, path.at(-1), EPSILON);
        assertArrayEquals(new float[] {9, 8}, path.at(2), EPSILON);
        assertArrayEquals(new float[] {1, 2}, path.at(Double.NaN), EPSILON);
    }

    @Test
    public void repeatedPointsDoNotDivideByZero() {
        TouchPath still = new TouchPath(new float[] {5, 5}, new float[] {5, 5});
        assertArrayEquals(new float[] {5, 5}, still.at(0.5), EPSILON);

        TouchPath path = new TouchPath(new float[] {0, 0, 10}, new float[] {0, 0, 0});
        assertArrayEquals(new float[] {5, 0}, path.at(0.5), EPSILON);
    }

    @Test
    public void needsAtLeastTwoPoints() {
        try {
            new TouchPath(new float[] {1}, new float[] {1});
            fail();
        } catch (IllegalArgumentException expected) {
            // 至少两个点
        }
    }
}
