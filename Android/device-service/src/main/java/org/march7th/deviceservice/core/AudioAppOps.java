package org.march7th.deviceservice.core;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 服务和善后子进程共用的 PLAY_AUDIO 操作。 */
final class AudioAppOps {
    private static final String OP = "PLAY_AUDIO";
    private static final int OP_PLAY_AUDIO = 28;
    private static final String API = "com.android.internal.app.IAppOpsService";
    private static final List<String> MODES = Arrays.asList("allow", "ignore", "deny", "default", "foreground");
    private static final Pattern MODE = Pattern.compile("(?m)^\\s*" + OP + ":\\s*(\\w+)");
    private static final long COMMAND_TIMEOUT_MS = 5000;

    private AudioAppOps() {
    }

    static int userId(int uid) {
        return uid / 100_000; // UserHandle.PER_USER_RANGE
    }

    /**
     * 当前模式。没有单独设置过的包按系统默认返回 allow。
     * 返回 default 表示有一条显式的 default 记录：音频服务只放行 allow，这种状态下应用没有声音。
     */
    static String mode(String packageName, int uid) throws IOException, InterruptedException {
        try {
            List<?> packages = (List<?>) Class.forName(API).getMethod("getOpsForPackage",
                    int.class, String.class, int[].class).invoke(SystemApis.asInterface(API, "appops"),
                    uid, packageName, new int[]{OP_PLAY_AUDIO});
            if (packages != null) {
                for (Object ops : packages) {
                    List<?> entries = (List<?>) ops.getClass().getMethod("getOps").invoke(ops);
                    for (Object entry : entries) {
                        int mode = (Integer) entry.getClass().getMethod("getMode").invoke(entry);
                        return MODES.get(mode);
                    }
                }
            }
            return "allow";
        } catch (ReflectiveOperationException | RuntimeException ignored) {
            return shellMode(packageName, uid);
        }
    }

    static String effectiveMode(String packageName, int uid) throws IOException, InterruptedException {
        try {
            int mode = (Integer) Class.forName(API).getMethod("checkOperation", int.class, int.class, String.class)
                    .invoke(SystemApis.asInterface(API, "appops"), OP_PLAY_AUDIO, uid, packageName);
            return MODES.get(mode);
        } catch (ReflectiveOperationException | RuntimeException ignored) {
            return mode(packageName, uid);
        }
    }

    private static String shellMode(String packageName, int uid) throws IOException, InterruptedException {
        Shell.Result result = Shell.run(COMMAND_TIMEOUT_MS, "cmd", "appops", "get",
                "--user", Integer.toString(userId(uid)), packageName, OP);
        if (!result.ok()) {
            throw new IOException("appops get failed: " + result);
        }
        return parseMode(result.stdout);
    }

    static String parseMode(String output) {
        Matcher matcher = MODE.matcher(output);
        return matcher.find() ? matcher.group(1) : "allow";
    }

    /** 只写包级 AppOps，调用方负责回读和恢复原模式。 */
    static void setModeAndWait(String packageName, int uid, String mode) throws IOException, InterruptedException {
        int value = MODES.indexOf(mode);
        if (value >= 0) {
            try {
                Class.forName(API).getMethod("setMode", int.class, int.class, String.class, int.class)
                        .invoke(SystemApis.asInterface(API, "appops"), OP_PLAY_AUDIO, uid, packageName, value);
                return;
            } catch (ReflectiveOperationException | RuntimeException ignored) {
                // 个别系统只开放 shell 命令入口；在同一进程等写完再恢复。
            }
        }
        Shell.Result result = Shell.run(0, "cmd", "appops", "set",
                "--user", Integer.toString(userId(uid)), packageName, OP, mode);
        if (!result.ok() || !result.stderr.trim().isEmpty()) {
            throw new IOException("appops set failed: " + result);
        }
    }
}
