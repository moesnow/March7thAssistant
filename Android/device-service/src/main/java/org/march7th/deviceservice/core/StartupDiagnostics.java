package org.march7th.deviceservice.core;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** 启动已判定无画面时取一次系统侧证据。ROM 的文本格式差异只影响诊断字段。 */
final class StartupDiagnostics {
    private static final Pattern WINDOW_FIELDS = Pattern.compile(
            "(mDisplayId|taskId|mHasSurface|isOnScreen|isVisible|isReadyForDisplay\\(\\))=(\\d+|true|false)");
    private static final Pattern DISPLAY = Pattern.compile("Display: mDisplayId=(\\d+)");
    private static final Pattern LAYER = Pattern.compile(
            "^(?:[-+*]\\s*)?(?:(?:Output )?Layer|[a-zA-Z]+Layer)\\b");
    private static final Pattern BUFFER = Pattern.compile(
            "\\b(?:composition type|slot|isVisible|buffer|frame|frameNumber|activeBuffer)\\s*=\\s*"
                    + "(?:\\[[^\\]]{0,80}\\]|[-\\w.]+)", Pattern.CASE_INSENSITIVE);

    private StartupDiagnostics() {}

    static JSONObject collect(JSONObject out, JSONObject watchdog, int displayId) throws JSONException {
        return collect(out, watchdog, displayId, Long.MAX_VALUE);
    }

    static JSONObject collect(JSONObject out, JSONObject watchdog, int displayId, long deadline) throws JSONException {
        if (watchdog == null || displayId < 0 || watchdog.optInt("target_display_id", -1) != displayId) return out;
        String pkg = watchdog.getString("package");
        String windows = dump(out, "window", deadline, "dumpsys", "-t", "1", "window", pkg);
        out.put("windows", gameWindows(windows, pkg));

        // 服务端只保留目标游戏层的渲染字段，限制系统 dump 占用的内存。
        String layers = dump(out, "layers", deadline, "sh", "-c", "dumpsys -t 1 SurfaceFlinger | head -c 1048576");
        out.put("game_layers", gameLayers(layers, pkg));
        int pid = watchdog.optInt("pid", -1);
        if (pid > 0) {
            String errors = dump(out, "logcat", deadline, "logcat", "-d", "-t", "80", "--pid=" + pid, "-v", "brief",
                    "BLASTBufferQueue:W", "BufferQueueProducer:W", "BufferQueueConsumer:W", "libEGL:W",
                    "OpenGLRenderer:W", "SurfaceView:W", "*:S");
            JSONArray recent = new JSONArray();
            for (String line : errors.split("\n")) {
                if ((line.startsWith("W/") || line.startsWith("E/")) && recent.length() < 8) {
                    recent.put(line.substring(0, Math.min(line.length(), 240)));
                }
            }
            out.put("graphics_warnings", recent);
        }
        // 最后读取焦点，供单次恢复在注入前判断；缺字段不能当成没有焦点。
        return collectFocus(out, pkg, displayId, deadline);
    }

    static JSONObject collectFocus(JSONObject out, String pkg, int displayId) throws JSONException {
        return collectFocus(out, pkg, displayId, Long.MAX_VALUE);
    }

    static JSONObject collectFocus(JSONObject out, String pkg, int displayId, long deadline) throws JSONException {
        String displays = dump(out, "focus", deadline, "dumpsys", "-t", "1", "window", "displays");
        return out.put("target_window_focus", windowFocus(displays, pkg, displayId));
    }

    static String windowFocus(String dump, String pkg, int displayId) {
        boolean target = false;
        int indent = -1;
        for (String line : dump.split("\n")) {
            String content = line.trim();
            Matcher id = DISPLAY.matcher(content);
            if (id.find()) {
                target = Integer.toString(displayId).equals(id.group(1));
                indent = line.indexOf(content);
            } else if (!content.isEmpty() && (line.indexOf(content) < indent || content.startsWith("WINDOW MANAGER"))) {
                target = false;
            }
            if (target && content.startsWith("mCurrentFocus=")) {
                return content.contains(pkg + "/") ? "game" : content.endsWith("=null") ? "none" : "other";
            }
        }
        return "unknown";
    }

    static JSONArray gameWindows(String dump, String pkg) throws JSONException {
        JSONArray windows = new JSONArray();
        JSONObject window = null;
        int indent = -1;
        Pattern component = Pattern.compile(Pattern.quote(pkg) + "/[a-zA-Z0-9_.$]+");
        for (String line : dump.split("\n")) {
            String content = line.trim();
            if (content.startsWith("Window #")) {
                Matcher name = component.matcher(line);
                window = name.find() && windows.length() < 12 ? new JSONObject().put("activity", name.group()) : null;
                indent = line.indexOf(content);
                if (window != null) windows.put(window);
            } else if (!content.isEmpty() && line.indexOf(content) <= indent) {
                // Window 结束后的全局字段、缓存和厂商区段不属于这个窗口。
                window = null;
            } else if (window != null) {
                Matcher field = WINDOW_FIELDS.matcher(line);
                while (field.find()) window.put(field.group(1), field.group(2));
            }
        }
        return windows;
    }

    static JSONObject gameLayers(String dump, String pkg) throws JSONException {
        JSONObject layers = new JSONObject();
        String layer = null;
        int indent = 0;
        for (String line : dump.split("\n")) {
            String content = line.trim();
            if (LAYER.matcher(content).find()) {
                layer = content.contains(pkg + "/") ? content.substring(0, Math.min(content.length(), 220)) : null;
                indent = line.indexOf(content);
            } else if (content.isEmpty() || line.indexOf(content) <= indent) {
                layer = null;
            } else if (layer != null) {
                Matcher field = BUFFER.matcher(content);
                while (field.find()) {
                    if (!layers.has(layer) && layers.length() < 12) layers.put(layer, new JSONArray());
                    JSONArray fields = layers.optJSONArray(layer);
                    if (fields != null && fields.length() < 12) fields.put(field.group());
                }
            }
        }
        return layers;
    }

    private static String dump(JSONObject out, String field, long deadline, String... command) throws JSONException {
        try {
            long remaining = deadline - android.os.SystemClock.elapsedRealtime();
            if (remaining <= 0 || Thread.currentThread().isInterrupted()) {
                out.put(field + "_error", remaining <= 0 ? "deadline" : "stopped");
                return "";
            }
            Shell.Result result = Shell.run(Math.min(1200, remaining), command);
            if (result.ok()) return result.stdout;
            out.put(field + "_error", "exit=" + result.exitCode);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } catch (Exception e) {
            out.put(field + "_error", Logger.describe(e));
        }
        return "";
    }
}
