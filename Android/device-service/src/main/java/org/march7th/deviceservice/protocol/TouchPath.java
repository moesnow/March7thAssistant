package org.march7th.deviceservice.protocol;

/** 滑动轨迹：按路程在折线上匀速取点。 */
public final class TouchPath {
    private final float[] xs;
    private final float[] ys;
    /** cumulative[i] 是从起点到第 i 个点的路程。 */
    private final double[] cumulative;

    public TouchPath(float[] xs, float[] ys) {
        if (xs.length != ys.length || xs.length < 2) {
            throw new IllegalArgumentException("a path needs at least two points");
        }
        this.xs = xs.clone();
        this.ys = ys.clone();
        cumulative = new double[xs.length];
        for (int i = 1; i < xs.length; i++) {
            cumulative[i] = cumulative[i - 1] + Math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]);
        }
    }

    /**
     * 取路程比例 fraction 处的坐标。
     *
     * @param fraction 0 为起点，1 为终点，超出范围时取端点
     * @return {x, y}
     */
    public float[] at(double fraction) {
        int last = xs.length - 1;
        if (!(fraction > 0)) {
            return new float[] {xs[0], ys[0]};
        }
        double total = cumulative[last];
        if (fraction >= 1 || total == 0) {
            return new float[] {xs[last], ys[last]};
        }
        double target = fraction * total;
        int segment = 1;
        while (segment < last && cumulative[segment] < target) {
            segment++;
        }
        double length = cumulative[segment] - cumulative[segment - 1];
        double t = length == 0 ? 1 : (target - cumulative[segment - 1]) / length;
        return new float[] {
                (float) (xs[segment - 1] + (xs[segment] - xs[segment - 1]) * t),
                (float) (ys[segment - 1] + (ys[segment] - ys[segment - 1]) * t),
        };
    }
}
