package org.march7th.deviceservice.core;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.function.Consumer;

/** app_process 只需要 ActivityThread 的系统 Context，不执行系统进程专用的完整 attach。 */
final class SystemContext {
    private SystemContext() {
    }

    static Object resolve(int sdk, ClassLoader loader, Consumer<String> trace) throws ReflectiveOperationException {
        if (sdk < 34) {
            return null;
        }
        String stage = "ActivityThread";
        Field current = null;
        Object published = null;
        Throwable configFailure = null;
        try {
            Class<?> activityThread = loader.loadClass("android.app.ActivityThread");
            stage = "ActivityThread.sCurrentActivityThread";
            current = activityThread.getDeclaredField("sCurrentActivityThread");
            current.setAccessible(true);
            Object thread = current.get(null);
            if (thread == null) {
                stage = "ActivityThread.<init>";
                Constructor<?> constructor = activityThread.getDeclaredConstructor();
                constructor.setAccessible(true);
                thread = constructor.newInstance();
                trace.accept("ActivityThread constructed");

                stage = "ActivityThread.mSystemThread";
                Field system = activityThread.getDeclaredField("mSystemThread");
                system.setAccessible(true);
                system.setBoolean(thread, true);
                stage = "ActivityThread.sCurrentActivityThread.set";
                current.set(null, thread);
                published = thread;
                trace.accept("system ActivityThread registered");

                // AOSP 的 attach 会先建立配置控制器。部分 ROM 在 getSystemContext 取显示信息时就会用到它。
                // 若厂商改变了该私有接口，仍允许其原有的 getSystemContext 实现工作。
                try {
                    Field config = activityThread.getDeclaredField("mConfigurationController");
                    config.setAccessible(true);
                    if (config.get(thread) == null) {
                        Constructor<?> init = config.getType().getDeclaredConstructor(
                                loader.loadClass("android.app.ActivityThreadInternal"));
                        init.setAccessible(true);
                        config.set(thread, init.newInstance(thread));
                    }
                    trace.accept("ActivityThread.mConfigurationController ready");
                } catch (ReflectiveOperationException | RuntimeException | LinkageError e) {
                    configFailure = e;
                    trace.accept("ActivityThread.mConfigurationController unavailable: " + Logger.stackTrace(e));
                }
            } else {
                trace.accept("using existing ActivityThread");
            }

            stage = "ActivityThread.getSystemContext";
            Method getSystemContext = activityThread.getDeclaredMethod("getSystemContext");
            getSystemContext.setAccessible(true);
            Object base = getSystemContext.invoke(thread);
            if (base == null) {
                throw new IllegalStateException("returned null");
            }
            return base;
        } catch (ReflectiveOperationException | RuntimeException | LinkageError e) {
            ReflectiveOperationException failure = new ReflectiveOperationException(stage + ": " + Logger.describe(e), e);
            if (configFailure != null) {
                failure.addSuppressed(configFailure);
            }
            if (published != null) {
                try {
                    if (current.get(null) == published) {
                        current.set(null, null);
                    }
                } catch (ReflectiveOperationException | RuntimeException cleanup) {
                    failure.addSuppressed(cleanup);
                }
            }
            throw failure;
        }
    }
}
