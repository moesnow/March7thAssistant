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
        if (watchdog == null || displayId < 0 || watchdog.optInt("target_display_id", -1) != displayId) return out;
        String pkg = watchdog.getString("package");
        String windows = dump(out, "window", "dumpsys", "-t", "1", "window", pkg);
        out.put("windows", gameWindows(windows, pkg));

        String displays = dump(out, "focus", "dumpsys", "-t", "1", "window", "displays");
        boolean target = false;
        for (String line : displays.split("\n")) {
            Matcher id = DISPLAY.matcher(line);
            if (id.find()) target = Integer.toString(displayId).equals(id.group(1));
            if (target && line.trim().startsWith("mCurrentFocus=")) {
                out.put("target_window_focus", line.contains(pkg + "/") ? "game"
                        : line.trim().endsWith("=null") ? "none" : "other");
            }
        }

        // 服务端只保留目标游戏层的渲染字段，限制系统 dump 占用的内存。
        String layers = dump(out, "layers", "sh", "-c", "dumpsys -t 1 SurfaceFlinger | head -c 1048576");
        out.put("game_layers", gameLayers(layers, pkg));
        int pid = watchdog.optInt("pid", -1);
        if (pid > 0) {
            String errors = dump(out, "logcat", "logcat", "-d", "-t", "80", "--pid=" + pid, "-v", "brief",
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
        return out;
    }

    static JSONArray gameWindows(String dump, String pkg) throws JSONException {
        JSONArray windows = new JSONArray();
        JSONObject window = null;
        Pattern component = Pattern.compile(Pattern.quote(pkg) + "/[a-zA-Z0-9_.$]+");
        for (String line : dump.split("\n")) {
            if (line.trim().startsWith("Window #")) {
                Matcher name = component.matcher(line);
                window = name.find() && windows.length() < 12 ? new JSONObject().put("activity", name.group()) : null;
                if (window != null) windows.put(window);
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

    private static String dump(JSONObject out, String field, String... command) throws JSONException {
        try {
            Shell.Result result = Shell.run(1200, command);
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
