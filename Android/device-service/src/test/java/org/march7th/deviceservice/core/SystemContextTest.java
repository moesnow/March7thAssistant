package org.march7th.deviceservice.core;

import org.junit.After;
import org.junit.Test;

import java.lang.reflect.InvocationTargetException;
import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.*;

public class SystemContextTest {
    interface ThreadInternal {}

    static class Configuration {
        final ThreadInternal owner;
        private Configuration(ThreadInternal owner) { this.owner = owner; }
    }

    static class ThreadWithConfig implements ThreadInternal {
        static ThreadWithConfig sCurrentActivityThread;
        static boolean failGetter;
        boolean mSystemThread;
        Configuration mConfigurationController;

        public Object getSystemContext() {
            if (failGetter) {
                throw new SecurityException("getSystemContext denied");
            }
            // 部分 ROM 在生成 base 前通过全局线程读取配置。
            return sCurrentActivityThread.mConfigurationController.owner;
        }
    }

    static class VendorThread {
        static VendorThread sCurrentActivityThread;
        boolean mSystemThread;
        static Object base;
        public Object getSystemContext() { return base; }
    }

    static class BrokenConstructor {
        static BrokenConstructor sCurrentActivityThread;
        private BrokenConstructor() { throw new IllegalStateException("no looper"); }
    }

    static class MissingSystemFlag {
        static MissingSystemFlag sCurrentActivityThread;
    }

    private final List<String> trace = new ArrayList<>();

    private Object resolve(int sdk, Class<?> threadType) throws ReflectiveOperationException {
        ClassLoader framework = new ClassLoader() {
            @Override public Class<?> loadClass(String name) throws ClassNotFoundException {
                if (sdk < 34) throw new AssertionError("legacy path loaded " + name);
                if ("android.app.ActivityThreadInternal".equals(name)) return ThreadInternal.class;
                if ("android.app.ActivityThread".equals(name) && threadType != null) return threadType;
                throw new ClassNotFoundException(name);
            }
        };
        return SystemContext.resolve(sdk, framework, trace::add);
    }

    @After public void reset() {
        ThreadWithConfig.sCurrentActivityThread = null;
        ThreadWithConfig.failGetter = false;
        VendorThread.sCurrentActivityThread = null;
        VendorThread.base = null;
    }

    @Test public void legacyVersionsDoNotTouchActivityThread() throws Exception {
        for (int sdk = 29; sdk <= 33; ++sdk) assertNull(resolve(sdk, null));
    }

    @Test public void registersConfiguredSystemThreadBeforeObtainingBase() throws Exception {
        Object base = resolve(34, ThreadWithConfig.class);
        assertNotNull(base);
        assertSame(ThreadWithConfig.sCurrentActivityThread, base);
        assertTrue(ThreadWithConfig.sCurrentActivityThread.mSystemThread);
    }

    @Test public void reusesExistingThreadWithoutChangingItsIdentityOrConfiguration() throws Exception {
        ThreadWithConfig existing = new ThreadWithConfig();
        Configuration original = new Configuration(existing);
        existing.mConfigurationController = original;
        ThreadWithConfig.sCurrentActivityThread = existing;
        assertSame(existing, resolve(36, ThreadWithConfig.class));
        assertSame(original, existing.mConfigurationController);
        assertFalse(existing.mSystemThread);
        ThreadWithConfig.failGetter = true;
        assertThrows(ReflectiveOperationException.class, () -> resolve(36, ThreadWithConfig.class));
        assertSame(existing, ThreadWithConfig.sCurrentActivityThread);
    }

    @Test public void acceptsWorkingVendorContextWithoutKnownConfigurationField() throws Exception {
        VendorThread.base = new Object();
        assertSame(VendorThread.base, resolve(36, VendorThread.class));
        assertTrue(trace.stream().anyMatch(s -> s.contains("NoSuchFieldException")));
    }

    @Test public void nullBasePreservesOptionalStepFailureAndRollsBackPublishedThread() {
        ReflectiveOperationException failure = assertThrows(ReflectiveOperationException.class,
                () -> resolve(36, VendorThread.class));
        assertTrue(failure.getMessage().contains("ActivityThread.getSystemContext: IllegalStateException: returned null"));
        assertTrue(failure.getSuppressed()[0] instanceof NoSuchFieldException);
        assertNull(VendorThread.sCurrentActivityThread);
    }

    @Test public void reportsHiddenApiFailureAtItsOriginalStage() {
        assertStage(null, "ActivityThread: ClassNotFoundException");
        assertStage(Object.class, "ActivityThread.sCurrentActivityThread: NoSuchFieldException");
        assertStage(BrokenConstructor.class, "ActivityThread.<init>: IllegalStateException");
        assertStage(MissingSystemFlag.class, "ActivityThread.mSystemThread: NoSuchFieldException");
        ThreadWithConfig.failGetter = true;
        Throwable failure = assertStage(ThreadWithConfig.class, "ActivityThread.getSystemContext: SecurityException");
        assertTrue(failure.getCause() instanceof InvocationTargetException);
        assertTrue(failure.getCause().getCause() instanceof SecurityException);
        assertNull(ThreadWithConfig.sCurrentActivityThread);
    }

    private Throwable assertStage(Class<?> thread, String expected) {
        Throwable failure = assertThrows(ReflectiveOperationException.class, () -> resolve(34, thread));
        assertTrue(failure.getMessage(), failure.getMessage().contains(expected));
        return failure;
    }
}
