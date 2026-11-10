package org.march7th.deviceservice.core;

import android.content.ComponentName;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.protocol.StackEntry;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * 通过反射调用的系统隐藏接口，集中放在这里，按系统版本分支。
 *
 * 实机验证过的只有 Android 10（Redmi Note 7，MIUI 12.5）；Android 12 在 MuMu 模拟器上验证过。
 * 标着“未在实机验证”的分支参照 scrcpy（Apache-2.0）的做法编写。
 */
final class SystemApis {
    private static Object activityTaskManager;
    private static Object windowManager;
    private static Object powerManager;
    private static Object displayManagerGlobal;

    private SystemApis() {
    }

    static IBinder service(String name) throws ReflectiveOperationException {
        return (IBinder) Class.forName("android.os.ServiceManager").getMethod("getService", String.class).invoke(null, name);
    }

    private static Object asInterface(String interfaceName, String serviceName) throws ReflectiveOperationException {
        IBinder binder = service(serviceName);
        if (binder == null) {
            throw new IllegalStateException("system service not found: " + serviceName);
        }
        return Class.forName(interfaceName + "$Stub").getMethod("asInterface", IBinder.class).invoke(null, binder);
    }

    private static Method method(String className, String name, Class<?>... types) throws ReflectiveOperationException {
        return Class.forName(className).getMethod(name, types);
    }

    private static Method methodByName(String className, String name) throws ReflectiveOperationException {
        for (Method method : Class.forName(className).getMethods()) {
            if (method.getName().equals(name)) {
                return method;
            }
        }
        throw new NoSuchMethodException(className + "." + name);
    }

    // ---- 进程 ----

    /** 读 /proc/&lt;pid&gt;/cmdline 的第一个参数，进程不存在时返回 null。 */
    static String processName(int pid) {
        byte[] buffer = new byte[256];
        try (FileInputStream in = new FileInputStream("/proc/" + pid + "/cmdline")) {
            int n = in.read(buffer);
            if (n <= 0) {
                return null;
            }
            int end = 0;
            while (end < n && buffer[end] != 0) {
                end++;
            }
            return new String(buffer, 0, end, StandardCharsets.UTF_8);
        } catch (IOException e) {
            return null;
        }
    }

    /** 按进程名找 pid，找不到返回 -1。shell 属于 readproc 组，能看到其他用户的进程。 */
    static int findProcess(String name) {
        String[] entries = new File("/proc").list();
        if (entries == null) {
            return -1;
        }
        for (String entry : entries) {
            if (entry.isEmpty() || entry.charAt(0) < '0' || entry.charAt(0) > '9') {
                continue;
            }
            int pid;
            try {
                pid = Integer.parseInt(entry);
            } catch (NumberFormatException e) {
                continue;
            }
            if (name.equals(processName(pid))) {
                return pid;
            }
        }
        return -1;
    }

    // ---- 显示器 ----

    private static synchronized Object displayManagerGlobal() throws ReflectiveOperationException {
        if (displayManagerGlobal == null) {
            displayManagerGlobal = method("android.hardware.display.DisplayManagerGlobal", "getInstance").invoke(null);
        }
        return displayManagerGlobal;
    }

    static int[] displayIds() throws ReflectiveOperationException {
        Object global = displayManagerGlobal();
        return (int[]) global.getClass().getMethod("getDisplayIds").invoke(global);
    }

    /** 读一个显示器的逻辑尺寸等信息，显示器不存在时返回 null。 */
    static JSONObject displayInfo(int displayId) throws ReflectiveOperationException, JSONException {
        Object global = displayManagerGlobal();
        Object info = global.getClass().getMethod("getDisplayInfo", int.class).invoke(global, displayId);
        if (info == null) {
            return null;
        }
        JSONObject json = new JSONObject();
        json.put("id", displayId);
        json.put("width", intField(info, "logicalWidth"));
        json.put("height", intField(info, "logicalHeight"));
        json.put("dpi", intField(info, "logicalDensityDpi"));
        json.put("rotation", intField(info, "rotation"));
        json.put("flags", intField(info, "flags"));
        json.put("state", intField(info, "state"));
        json.put("type", intField(info, "type"));
        Object name = field(info, "name");
        json.put("name", name == null ? JSONObject.NULL : name.toString());
        Object owner = field(info, "ownerPackageName");
        json.put("owner", owner == null ? JSONObject.NULL : owner.toString());
        return json;
    }

    private static Object field(Object target, String name) throws ReflectiveOperationException {
        Field field = target.getClass().getField(name);
        return field.get(target);
    }

    private static int intField(Object target, String name) throws ReflectiveOperationException {
        return target.getClass().getField(name).getInt(target);
    }

    // ---- 任务 ----

    private static synchronized Object activityTaskManager() throws ReflectiveOperationException {
        if (activityTaskManager == null) {
            activityTaskManager = method("android.app.ActivityTaskManager", "getService").invoke(null);
        }
        return activityTaskManager;
    }

    /**
     * 列出全部任务栈。需要 MANAGE_ACTIVITY_STACKS（Android 10、11）或 MANAGE_ACTIVITY_TASKS（Android 12 起），shell 都有。
     *
     * Android 10、11：IActivityTaskManager.getAllStackInfos()，元素是 ActivityManager.StackInfo。
     * Android 12 起：getAllRootTaskInfos()，元素是 ActivityTaskManager.RootTaskInfo（未在实机验证，MuMu 上通过）。
     */
    static List<StackEntry> stacks() throws ReflectiveOperationException {
        Object service = activityTaskManager();
        Class<?> api = Class.forName("android.app.IActivityTaskManager");
        boolean rootTasks = Build.VERSION.SDK_INT >= 31;
        List<?> infos = (List<?>) api.getMethod(rootTasks ? "getAllRootTaskInfos" : "getAllStackInfos").invoke(service);
        List<StackEntry> result = new ArrayList<>();
        if (infos == null) {
            return result;
        }
        for (Object info : infos) {
            ComponentName top = (ComponentName) field(info, "topActivity");
            StackEntry entry = new StackEntry(
                    intField(info, rootTasks ? "taskId" : "stackId"),
                    intField(info, "displayId"),
                    (Boolean) field(info, "visible"),
                    top == null ? null : top.getPackageName() + "/" + top.getClassName());
            int[] ids = (int[]) field(info, rootTasks ? "childTaskIds" : "taskIds");
            String[] names = (String[]) field(info, rootTasks ? "childTaskNames" : "taskNames");
            for (int i = 0; ids != null && i < ids.length; i++) {
                entry.taskIds.add(ids[i]);
                entry.taskNames.add(names != null && i < names.length ? names[i] : null);
            }
            result.add(entry);
        }
        return result;
    }

    /**
     * 把任务栈移到另一个显示器。
     *
     * Android 10、11：moveStackToDisplay(stackId, displayId)。
     * Android 12 起：moveRootTaskToDisplay(rootTaskId, displayId)（未在实机验证，MuMu 上通过）。
     */
    static void moveStackToDisplay(int stackId, int displayId) throws ReflectiveOperationException {
        Object service = activityTaskManager();
        Class<?> api = Class.forName("android.app.IActivityTaskManager");
        Method move;
        try {
            move = api.getMethod("moveRootTaskToDisplay", int.class, int.class);
        } catch (NoSuchMethodException older) {
            move = api.getMethod("moveStackToDisplay", int.class, int.class);
        }
        move.invoke(service, stackId, displayId);
    }

    // ---- 电源与锁屏 ----

    private static synchronized Object windowManager() throws ReflectiveOperationException {
        if (windowManager == null) {
            windowManager = asInterface("android.view.IWindowManager", "window");
        }
        return windowManager;
    }

    private static synchronized Object powerManager() throws ReflectiveOperationException {
        if (powerManager == null) {
            powerManager = asInterface("android.os.IPowerManager", "power");
        }
        return powerManager;
    }

    static boolean keyguardLocked() throws ReflectiveOperationException {
        return (Boolean) method("android.view.IWindowManager", "isKeyguardLocked").invoke(windowManager());
    }

    /** 系统是否处于唤醒（可交互）状态。只关面板不改变这个状态。 */
    static boolean interactive() throws ReflectiveOperationException {
        return (Boolean) method("android.os.IPowerManager", "isInteractive").invoke(powerManager());
    }

    /**
     * 重置系统的息屏计时，效果等同于用户碰了一下屏幕。需要 DEVICE_POWER，shell 有。
     *
     * Android 10、11 的签名是 userActivity(time, event, flags)；Android 12 起多了第一个参数 displayId（未在实机验证）。
     */
    static void userActivity() throws ReflectiveOperationException {
        Method poke = methodByName("android.os.IPowerManager", "userActivity");
        long now = SystemClock.uptimeMillis();
        if (poke.getParameterTypes().length == 3) {
            poke.invoke(powerManager(), now, 0, 0);
        } else {
            poke.invoke(powerManager(), 0, now, 0, 0);
        }
    }

    /**
     * 只开关实体面板，不改变系统的唤醒状态。
     *
     * Android 10 到 13：SurfaceControl.getInternalDisplayToken() 加 setDisplayPowerMode()。
     * Android 14 起取显示令牌的接口挪到了 services.jar 里的 DisplayControl（未在实机验证）。
     */
    static void setPanelPower(boolean on) throws ReflectiveOperationException {
        int mode = on ? 2 : 0; // POWER_MODE_NORMAL : POWER_MODE_OFF
        Class<?> surfaceControl = Class.forName("android.view.SurfaceControl");
        Method setMode = surfaceControl.getMethod("setDisplayPowerMode", IBinder.class, int.class);
        if (Build.VERSION.SDK_INT < 34) {
            IBinder token = (IBinder) surfaceControl.getMethod("getInternalDisplayToken").invoke(null);
            if (token == null) {
                throw new IllegalStateException("no internal display token");
            }
            setMode.invoke(null, token, mode);
            return;
        }
        Class<?> displayControl = loadDisplayControl();
        long[] ids = (long[]) displayControl.getMethod("getPhysicalDisplayIds").invoke(null);
        if (ids == null || ids.length == 0) {
            throw new IllegalStateException("no physical display");
        }
        Method getToken = displayControl.getMethod("getPhysicalDisplayToken", long.class);
        for (long id : ids) {
            setMode.invoke(null, (IBinder) getToken.invoke(null, id), mode);
        }
    }

    private static Class<?> loadDisplayControl() throws ReflectiveOperationException {
        Class<?> factory = Class.forName("com.android.internal.os.ClassLoaderFactory");
        Method create = factory.getDeclaredMethod("createClassLoader", String.class, String.class, String.class,
                ClassLoader.class, int.class, boolean.class, String.class);
        ClassLoader loader = (ClassLoader) create.invoke(null, "/system/framework/services.jar", null, null,
                ClassLoader.getSystemClassLoader(), 0, true, null);
        Class<?> displayControl = loader.loadClass("com.android.server.display.DisplayControl");
        Method loadLibrary = Runtime.class.getDeclaredMethod("loadLibrary0", Class.class, String.class);
        loadLibrary.setAccessible(true);
        loadLibrary.invoke(Runtime.getRuntime(), displayControl, "android_servers");
        return displayControl;
    }
}
