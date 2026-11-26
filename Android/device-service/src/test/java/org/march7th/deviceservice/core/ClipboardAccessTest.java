package org.march7th.deviceservice.core;

import org.junit.Test;

import java.lang.reflect.InvocationTargetException;

import static org.junit.Assert.*;

public class ClipboardAccessTest {
    public static class Android10 {
        Object[] received;

        public void setPrimaryClip(String clip, String name, int user) {
            received = new Object[]{clip, name, user};
        }
    }

    public static class WithAttribution {
        Object[] received;

        public void setPrimaryClip(String clip, String name, String attribution, int user) {
            received = new Object[]{clip, name, attribution, user};
        }
    }

    public static class WithDevice {
        Object[] received;

        public void setPrimaryClip(String clip, String name, String attribution, int user, int device) {
            received = new Object[]{clip, name, attribution, user, device};
        }
    }

    public static class WithUserOperation {
        Object[] received;

        public void setPrimaryClip(String clip, String name, String attribution, int user, int device, boolean operation) {
            received = new Object[]{clip, name, attribution, user, device, operation};
        }
    }

    public static class Denied extends Android10 {
        @Override
        public void setPrimaryClip(String clip, String name, int user) {
            throw new SecurityException("denied");
        }
    }

    @Test
    public void resolvesAndroidAndVendorSignaturesWithoutLosingUnicode() throws Exception {
        String text = "兑换码SR8888";
        Android10 old = new Android10();
        new ClipboardAccess(old, String.class, "com.android.shell", 0).set(text);
        assertArrayEquals(new Object[]{text, "com.android.shell", 0}, old.received);
        WithAttribution attributed = new WithAttribution();
        new ClipboardAccess(attributed, String.class, "com.android.shell", 10).set(text);
        assertArrayEquals(new Object[]{text, "com.android.shell", null, 10}, attributed.received);
        WithDevice device = new WithDevice();
        new ClipboardAccess(device, String.class, "com.android.shell", 0).set(text);
        assertArrayEquals(new Object[]{text, "com.android.shell", null, 0, 0}, device.received);
        WithUserOperation vendor = new WithUserOperation();
        new ClipboardAccess(vendor, String.class, "com.android.shell", 0).set(text);
        assertArrayEquals(new Object[]{text, "com.android.shell", null, 0, 0, true}, vendor.received);
    }

    @Test
    public void reportsUnavailableOrDeniedClipboard() throws Exception {
        assertThrows(NoSuchMethodException.class, () -> new ClipboardAccess(new Object(), String.class, "shell", 0));
        ClipboardAccess denied = new ClipboardAccess(new Denied(), String.class, "shell", 0);
        InvocationTargetException error = assertThrows(InvocationTargetException.class, () -> denied.set("code"));
        assertTrue(error.getCause() instanceof SecurityException);
    }
}
