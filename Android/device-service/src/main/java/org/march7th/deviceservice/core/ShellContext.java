package org.march7th.deviceservice.core;

import android.content.AttributionSource;
import android.content.Context;
import android.content.ContextWrapper;
import android.os.Build;
import android.os.Looper;
import android.os.Process;

import java.util.StringJoiner;

/**
 * 以 com.android.shell 的身份向系统服务报到的 Context。
 *
 * 进程由 app_process 直接启动，没有 Application，也就没有现成的 Context；而 DisplayManager 等接口要靠
 * Context 里的包名做权限校验。做法参照 scrcpy（Apache-2.0）的 FakeContext 与 Workarounds。
 *
 * Android 10 到 13 用空底座就够了：建虚拟屏只读包名，输入走 InputManager.getInstance()。
 * Android 14 起输入服务及新版 DisplayManager 会查询系统服务，这时才借一个系统 Context 做底座；
 * 在 MIUI 12.5 上构造系统 Context 会往标准错误打一段主题配置缺失的堆栈，所以低版本不去碰它。
 */
final class ShellContext extends ContextWrapper {
    static final String PACKAGE = "com.android.shell";

    private static ShellContext instance;
    private static ReflectiveOperationException initFailure;
    private static String initTrace;

    private ShellContext(Context base) {
        super(base);
    }

    /** API 34+ 的第一次调用在服务启动线程上进行，构造系统 Context 需要它已准备好的 Looper。 */
    static synchronized ShellContext get() throws ReflectiveOperationException {
        if (initFailure != null) {
            throw initFailure;
        }
        if (instance == null) {
            StringJoiner steps = new StringJoiner("\n");
            steps.add("shell context sdk=" + Build.VERSION.SDK_INT
                    + " mainLooper=" + (Looper.myLooper() != null && Looper.myLooper() == Looper.getMainLooper()));
            try {
                Context base = (Context) SystemContext.resolve(Build.VERSION.SDK_INT, ShellContext.class.getClassLoader(), steps::add);
                instance = new ShellContext(base);
                steps.add("base=" + (base == null ? "null (legacy)" : base.getClass().getName()));
            } catch (ReflectiveOperationException e) {
                // 当前进程只在已准备 Looper 的启动线程初始化一次；命令线程复用这次失败及其原始调用栈。
                initFailure = e;
                throw e;
            } finally {
                initTrace = steps.toString();
                Logger.i(initTrace);
            }
        }
        return instance;
    }

    static synchronized String initializationTrace() {
        return initTrace;
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
