package org.march7th.deviceservice.core;

import android.content.AttributionSource;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.Build;
import android.os.Process;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;

/**
 * 以 com.android.shell 的身份向系统服务报到的 Context。
 *
 * 进程由 app_process 直接启动，没有 Application，也就没有现成的 Context；而 DisplayManager 等接口要靠
 * Context 里的包名做权限校验。做法参照 scrcpy（Apache-2.0）的 FakeContext 与 Workarounds。
 *
 * Android 10 到 13 用空底座就够了：建虚拟屏只读包名，输入走 InputManager.getInstance()。
 * Android 14 起取 InputManager 要靠 Context，这时才借一个系统 Context 做底座（未在实机验证）；
 * 在 MIUI 12.5 上构造系统 Context 会往标准错误打一段主题配置缺失的堆栈，所以低版本不去碰它。
 */
final class ShellContext extends ContextWrapper {
    static final String PACKAGE = "com.android.shell";

    private static ShellContext instance;

    private ShellContext(Context base) {
        super(base);
    }

    /** 第一次调用必须在已经 prepare 过 Looper 的线程上（构造系统 Context 需要）。 */
    static synchronized ShellContext get() {
        if (instance == null) {
            instance = new ShellContext(Build.VERSION.SDK_INT >= 34 ? systemContextOrNull() : null);
        }
        return instance;
    }

    boolean hasBase() {
        return getBaseContext() != null;
    }

    private static Context systemContextOrNull() {
        try {
            Class<?> activityThread = Class.forName("android.app.ActivityThread");
            Constructor<?> constructor = activityThread.getDeclaredConstructor();
            constructor.setAccessible(true);
            Object thread = constructor.newInstance();
            Field current = activityThread.getDeclaredField("sCurrentActivityThread");
            current.setAccessible(true);
            current.set(null, thread);
            Field systemThread = activityThread.getDeclaredField("mSystemThread");
            systemThread.setAccessible(true);
            systemThread.setBoolean(thread, true);
            return (Context) activityThread.getDeclaredMethod("getSystemContext").invoke(thread);
        } catch (Throwable error) {
            Logger.w("system context unavailable, continuing without it", error);
            return null;
        }
    }

    @Override
    public String getPackageName() {
        return PACKAGE;
    }

    @Override
    public String getOpPackageName() {
        return PACKAGE;
    }

    /** Android 12 起框架用它取调用方身份。 */
    @Override
    public AttributionSource getAttributionSource() {
        return new AttributionSource.Builder(Process.SHELL_UID).setPackageName(PACKAGE).build();
    }

    @Override
    public String getAttributionTag() {
        return null;
    }

    /** Android 14 起建虚拟屏时会读设备 ID，0 表示默认设备。 */
    @Override
    public int getDeviceId() {
        return 0;
    }

    @Override
    public Context getApplicationContext() {
        return this;
    }

    /** 覆盖隐藏的 Context.getUserId()。 */
    public int getUserId() {
        return 0;
    }
}
