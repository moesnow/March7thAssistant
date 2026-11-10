package org.march7th.deviceservice.core;

import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Process;
import android.os.SystemClock;
import android.view.KeyEvent;
import android.view.MotionEvent;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.protocol.FrameEncoder;
import org.march7th.deviceservice.protocol.FrameSequencer;
import org.march7th.deviceservice.protocol.JsonIntegers;
import org.march7th.deviceservice.protocol.Message;
import org.march7th.deviceservice.protocol.Protocol;
import org.march7th.deviceservice.protocol.TouchPath;

import java.util.ArrayDeque;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.regex.Pattern;

/**
 * 设备端服务的核心：把一条请求变成一条响应，另外向订阅了的会话推送事件。
 *
 * 这里不关心请求从哪来。桌面模式由 {@code LocalSocketServer} 喂请求；APK 模式下 Shizuku UserService
 * 可以直接构造本类，自己实现传输。构造必须在已经 prepare 过 Looper 的线程上进行。
 */
public final class DeviceService implements Watchdog.Host {
    /** 点按的默认按压时长。Redmi Note 7 上实测 50 ms 打开手机菜单 20 次全部成功，见 PROTOCOL.md。 */
    public static final int DEFAULT_TAP_MS = 50;

    private static final Pattern COMPONENT = Pattern.compile("[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+");
    private static final Pattern PACKAGE = Pattern.compile("[A-Za-z0-9_.]+");
    private static final int EVENT_LOG_SIZE = 256;

    /** 事件的去向。实现里不要长时间阻塞。 */
    public interface EventSink {
        void onEvent(JSONObject event);
    }

    /** 一个已鉴权的客户端。同一个会话的请求必须串行提交。 */
    public static final class Session {
        public final int id;
        private final EventSink sink;
        private volatile boolean subscribed;
        // 取帧缓冲和上一次的编码结果，会话内复用
        private byte[] pixels;
        private String cacheKey;
        private long cacheSeq;
        private JSONObject cacheHeader;
        private byte[] cachePayload;
        private int cacheLength;

        private Session(int id, EventSink sink) {
            this.id = id;
            this.sink = sink;
        }
    }

    private final long startedAt = SystemClock.elapsedRealtime();
    private final HandlerThread captureThread = new HandlerThread("m7a-capture");
    private final Handler captureHandler;
    private final FrameSequencer sequencer = new FrameSequencer();
    private final InputInjector injector;
    private final SideEffects sideEffects;
    private final Object displayLock = new Object();
    private final List<Session> sessions = new CopyOnWriteArrayList<>();
    private final AtomicInteger nextSessionId = new AtomicInteger(1);
    private final ArrayDeque<JSONObject> eventLog = new ArrayDeque<>();
    private long eventSeq;
    private volatile VirtualScreen screen;
    private volatile Watchdog watchdog;
    private String lastLaunched; // displayLock
    private volatile boolean shutdownRequested;
    private volatile boolean closed;
    private ExecutorService encodePool;

    public DeviceService() throws ReflectiveOperationException {
        this(null);
    }

    /** cleanupJarPath 是善后进程可读取的设备端 DEX jar 路径；null 时沿用 CLASSPATH。 */
    public DeviceService(String cleanupJarPath) throws ReflectiveOperationException {
        ShellContext.get();
        captureThread.start();
        captureHandler = new Handler(captureThread.getLooper());
        injector = new InputInjector();
        sideEffects = new SideEffects(cleanupJarPath);
    }

    public Session openSession(EventSink sink, boolean subscribe) {
        Session session = new Session(nextSessionId.getAndIncrement(), sink);
        session.subscribed = subscribe;
        sessions.add(session);
        return session;
    }

    /** 会话结束：取消包含它的触点的手势。 */
    public void closeSession(Session session) {
        sessions.remove(session);
        injector.cancelAll(session.id, -1);
    }

    public int sessionCount() {
        return sessions.size();
    }

    /** 收到过 shutdown 之后为 true，传输层发完响应就应当停止服务。 */
    public boolean shutdownRequested() {
        return shutdownRequested;
    }

    /** 释放虚拟屏，恢复面板和静音，停掉看门狗。可以重复调用。 */
    public void close() {
        synchronized (displayLock) {
            if (closed) {
                return;
            }
            closed = true;
        }
        Watchdog dog = watchdog;
        watchdog = null;
        if (dog != null) {
            dog.stop();
        }
        injector.close();
        releaseDisplay();
        sideEffects.restoreAll();
        captureThread.quitSafely();
        synchronized (this) {
            if (encodePool != null) {
                encodePool.shutdownNow();
            }
        }
        Logger.i("service closed");
    }

    // ---- 请求分发 ----

    /** 处理一条请求。任何失败都变成错误响应，不抛异常。 */
    public Message handle(Session session, Message request) {
        JSONObject header = request.header;
        String command = header.optString("cmd", "");
        try {
            switch (command) {
                case "hello":
                    return new Message(describe(Message.ok(header)));
                case "status":
                    return new Message(status(Message.ok(header)));
                case "create_display":
                    return new Message(createDisplay(header));
                case "release_display":
                    releaseDisplay();
                    return new Message(Message.ok(header));
                case "launch":
                    return new Message(launch(header));
                case "stop_app":
                    return new Message(stopApp(header));
                case "frame":
                    return frame(session, header);
                case "tap":
                    return new Message(tap(session, header));
                case "swipe":
                    return new Message(swipe(session, header));
                case "touch":
                    return new Message(touch(session, header));
                case "key":
                    return new Message(key(header));
                case "focus":
                    return new Message(focus(header));
                case "watchdog":
                    return new Message(configureWatchdog(session, header));
                case "events":
                    return new Message(events(session, header));
                case "screen_power":
                    return new Message(screenPower(header));
                case "mute":
                    return new Message(mute(header));
                case "shutdown":
                    Logger.i("shutdown requested by session " + session.id);
                    shutdownRequested = true;
                    return new Message(Message.ok(header));
                default:
                    return new Message(Message.error(header, Protocol.E_UNKNOWN_COMMAND, "unknown command: " + command));
            }
        } catch (CommandException e) {
            JSONObject error = Message.error(header, e.code, e.getMessage());
            if (e.details != null) {
                try {
                    JSONObject body = error.getJSONObject("error");
                    Iterator<String> keys = e.details.keys();
                    while (keys.hasNext()) {
                        String key = keys.next();
                        body.put(key, e.details.get(key));
                    }
                } catch (JSONException ignored) {
                    // 附加字段写不进去不影响错误本身
                }
            }
            return new Message(error);
        } catch (JSONException | IllegalArgumentException e) {
            return new Message(Message.error(header, Protocol.E_BAD_REQUEST, String.valueOf(e.getMessage())));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new Message(Message.error(header, Protocol.E_INTERNAL, "interrupted"));
        } catch (Throwable error) {
            Logger.e("command " + command + " failed", error);
            return new Message(Message.error(header, Protocol.E_INTERNAL, Logger.describe(error)));
        }
    }

    // ---- hello 与 status ----

    private JSONObject describe(JSONObject out) throws JSONException {
        out.put("protocol", Protocol.VERSION);
        out.put("version", Protocol.SERVICE_VERSION);
        out.put("pid", Process.myPid());
        JSONObject device = new JSONObject();
        device.put("model", Build.MODEL);
        device.put("manufacturer", Build.MANUFACTURER);
        device.put("brand", Build.BRAND);
        device.put("device", Build.DEVICE);
        device.put("sdk", Build.VERSION.SDK_INT);
        device.put("release", Build.VERSION.RELEASE);
        device.put("abis", new JSONArray(java.util.Arrays.asList(Build.SUPPORTED_ABIS)));
        out.put("device", device);
        out.put("displays", displays());
        out.put("display", describeScreen(screen));
        out.put("frame_seq", sequencer.latest());
        out.put("encodings", new JSONArray(java.util.Arrays.asList(
                FrameEncoder.RGBA, FrameEncoder.RGB, FrameEncoder.RGB_ZLIB, FrameEncoder.RGBA_ZLIB)));
        out.put("features", new JSONArray(java.util.Arrays.asList(
                "screen_power", "mute", "stop_app", "events", "focus", "frame_after_ns")));
        out.put("default_tap_ms", DEFAULT_TAP_MS);
        return out;
    }

    private JSONArray displays() {
        JSONArray array = new JSONArray();
        try {
            for (int id : SystemApis.displayIds()) {
                JSONObject info = SystemApis.displayInfo(id);
                if (info != null) {
                    array.put(info);
                }
            }
        } catch (ReflectiveOperationException | JSONException | RuntimeException e) {
            Logger.w("cannot list displays", e);
        }
        return array;
    }

    private static Object describeScreen(VirtualScreen current) throws JSONException {
        if (current == null) {
            return JSONObject.NULL;
        }
        JSONObject json = new JSONObject();
        json.put("display_id", current.displayId);
        json.put("width", current.width);
        json.put("height", current.height);
        json.put("dpi", current.dpi);
        json.put("name", current.name);
        json.put("flags", current.flags);
        json.put("destroy_content", current.destroyContent);
        return json;
    }

    private JSONObject status(JSONObject out) throws JSONException {
        VirtualScreen current = screen;
        out.put("display", describeScreen(current));
        JSONObject frame = new JSONObject();
        frame.put("seq", sequencer.latest());
        FrameSequencer.Frame latest = current == null ? null : current.latestFrame();
        frame.put("age_ms", latest == null ? -1 : SystemClock.elapsedRealtime() - latest.acquiredMs);
        frame.put("capturing", sequencer.isActive());
        out.put("frame", frame);
        JSONObject power = new JSONObject();
        try {
            power.put("interactive", SystemApis.interactive());
            power.put("keyguard_locked", SystemApis.keyguardLocked());
        } catch (ReflectiveOperationException | RuntimeException e) {
            power.put("error", Logger.describe(e));
        }
        power.put("panel_off", sideEffects.panelOff());
        out.put("power", power);
        Watchdog dog = watchdog;
        out.put("watchdog", dog == null ? new JSONObject().put("enabled", false) : dog.describe());
        out.put("muted", new JSONArray(sideEffects.mutedPackages()));
        out.put("displays", displays());
        out.put("sessions", sessions.size());
        out.put("uptime_ms", SystemClock.elapsedRealtime() - startedAt);
        synchronized (eventLog) {
            out.put("event_seq", eventSeq);
        }
        return out;
    }

    // ---- 虚拟屏 ----

    private JSONObject createDisplay(JSONObject request) throws CommandException, JSONException {
        int width = request.optInt("width", 1280);
        int height = request.optInt("height", 720);
        int dpi = request.optInt("dpi", 240);
        String name = request.optString("name", "m7a-game");
        boolean destroyContent = request.optBoolean("destroy_content", true);
        if (width < 64 || width > 4096 || height < 64 || height > 4096 || dpi < 72 || dpi > 640) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "width and height must be 64..4096, dpi 72..640");
        }
        if (name.isEmpty() || name.length() > 64) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "name must be 1..64 characters");
        }
        synchronized (displayLock) {
            if (closed) {
                throw new CommandException(Protocol.E_INTERNAL, "service is closing");
            }
            VirtualScreen current = screen;
            boolean existing = current != null;
            if (existing) {
                if (current.width != width || current.height != height || current.dpi != dpi
                        || current.destroyContent != destroyContent) {
                    throw new CommandException(Protocol.E_DISPLAY_EXISTS,
                            "a " + current.width + "x" + current.height + "/" + current.dpi + " display already exists");
                }
            } else {
                try {
                    current = new VirtualScreen(name, width, height, dpi, destroyContent, sequencer, captureHandler);
                } catch (ReflectiveOperationException | RuntimeException e) {
                    Logger.e("cannot create virtual display", e);
                    throw new CommandException(Protocol.E_DISPLAY_FAILED, Logger.describe(e));
                }
                screen = current;
                Logger.i("virtual display " + current.displayId + " created: " + width + "x" + height + "/" + dpi
                        + " flags=0x" + Integer.toHexString(current.flags));
            }
            JSONObject out = Message.ok(request);
            out.put("display_id", current.displayId);
            out.put("width", current.width);
            out.put("height", current.height);
            out.put("dpi", current.dpi);
            out.put("flags", current.flags);
            out.put("existing", existing);
            return out;
        }
    }

    private void releaseDisplay() {
        synchronized (displayLock) {
            VirtualScreen current = screen;
            if (current == null) {
                return;
            }
            synchronized (injector) {
                injector.cancelAll(-1, current.displayId);
                screen = null;
                current.release();
            }
            Logger.i("virtual display " + current.displayId + " released");
        }
    }

    private VirtualScreen requireScreen() throws CommandException {
        VirtualScreen current = screen;
        if (current == null) {
            throw new CommandException(Protocol.E_NO_DISPLAY, "no virtual display; call create_display first");
        }
        return current;
    }

    /** 请求里显式给了 display_id 就用它（包括 0），否则用当前的虚拟屏。 */
    private int targetDisplay(JSONObject request) throws CommandException {
        if (request.has("display_id")) {
            return JsonIntegers.id(request.opt("display_id"), "display_id", Integer.MAX_VALUE);
        }
        return requireScreen().displayId;
    }

    // ---- 启动与停止应用 ----

    private JSONObject launch(JSONObject request) throws CommandException, JSONException, InterruptedException {
        String component = request.optString("component", "");
        if (!COMPONENT.matcher(component).matches()) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "component must look like package/class");
        }
        int displayId = targetDisplay(request);
        boolean wait = request.optBoolean("wait", true);
        int timeout = clamp(request.optInt("timeout_ms", 30000), 1000, 120000);
        long startedMs = SystemClock.elapsedRealtime();
        String output = startActivity(component, displayId, wait, timeout);
        synchronized (displayLock) {
            lastLaunched = component;
            Watchdog current = watchdog;
            if (current != null) {
                current.learnMainActivity(component);
            }
        }
        JSONObject out = Message.ok(request);
        out.put("display_id", displayId);
        out.put("output", output);
        out.put("seq", sequencer.latest());
        out.put("device_ms", startedMs);
        return out;
    }

    private String startActivity(String component, int displayId, boolean wait, int timeoutMs)
            throws CommandException, InterruptedException {
        Shell.Result result;
        try {
            if (wait) {
                result = Shell.run(timeoutMs, "cmd", "activity", "start-activity", "-W", "--display", Integer.toString(displayId),
                        "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-n", component);
            } else {
                result = Shell.run(timeoutMs, "cmd", "activity", "start-activity", "--display", Integer.toString(displayId),
                        "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-n", component);
            }
        } catch (java.io.IOException e) {
            throw new CommandException(Protocol.E_LAUNCH_FAILED, e.getMessage());
        }
        String text = (result.stdout + result.stderr).trim();
        if (!result.ok() || text.contains("Error:") || text.contains("Exception")) {
            throw new CommandException(Protocol.E_LAUNCH_FAILED, text);
        }
        Logger.i("launched " + component + " on display " + displayId);
        return text;
    }

    @Override
    public void launch(String component, int displayId) throws Exception {
        startActivity(component, displayId, false, 15000);
    }

    private JSONObject stopApp(JSONObject request) throws CommandException, InterruptedException {
        String packageName = request.optString("package", "");
        if (!PACKAGE.matcher(packageName).matches()) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "package is required");
        }
        try {
            Shell.Result result = Shell.run(10000, "cmd", "activity", "force-stop", packageName);
            if (!result.ok()) {
                throw new CommandException(Protocol.E_INTERNAL, result.toString());
            }
        } catch (java.io.IOException e) {
            throw new CommandException(Protocol.E_INTERNAL, e.getMessage());
        }
        Logger.i("force-stopped " + packageName);
        return Message.ok(request);
    }

    // ---- 取帧 ----

    private Message frame(Session session, JSONObject request) throws CommandException, JSONException, InterruptedException {
        VirtualScreen current = requireScreen();
        long minSeq = request.optLong("min_seq", 0);
        Long afterNs = request.has("after_ns") ? JsonIntegers.integer(request.opt("after_ns"), "after_ns") : null;
        int timeout = clamp(request.optInt("timeout_ms", 2000), 0, 30000);
        boolean allowStale = request.optBoolean("allow_stale", false);
        FrameEncoder.Options options = new FrameEncoder.Options();
        options.encoding = request.optString("encoding", FrameEncoder.RGB);
        options.level = request.optInt("level", 1);
        options.predictor = request.optString("predictor", FrameEncoder.PREDICTOR_NONE);
        options.chunks = request.optInt("chunks", 1);
        options.validate();

        int x = 0;
        int y = 0;
        int width = current.width;
        int height = current.height;
        JSONArray crop = request.optJSONArray("crop");
        if (crop != null) {
            if (crop.length() != 4) {
                throw new CommandException(Protocol.E_BAD_REQUEST, "crop must be [x, y, width, height]");
            }
            x = crop.getInt(0);
            y = crop.getInt(1);
            width = crop.getInt(2);
            height = crop.getInt(3);
            if (x < 0 || y < 0 || width <= 0 || height <= 0 || x > current.width - width || y > current.height - height) {
                throw new CommandException(Protocol.E_BAD_REQUEST,
                        "crop is outside the " + current.width + "x" + current.height + " display");
            }
        }

        String key = current.displayId + "/" + x + "," + y + "," + width + "," + height + "/" + options.cacheKey();
        int channels = options.channels();
        FrameSequencer.Frame captured;
        boolean stale = false;
        boolean cached;
        double copyMs = 0;
        long waitStart = System.nanoTime();
        double waitMs;
        synchronized (sequencer) {
            try {
                captured = current.awaitFrame(minSeq, afterNs, timeout);
            } catch (TimeoutException e) {
                captured = current.latestFrame();
                if (afterNs != null || !allowStale || captured == null) {
                    JSONObject details = new JSONObject().put("latest_seq", sequencer.latest());
                    if (afterNs != null && captured != null && !captured.timestampComparable) {
                        throw new CommandException(Protocol.E_FRAME_CLOCK_UNAVAILABLE,
                                "the latest frame timestamp cannot be compared with after_ns", details);
                    }
                    throw new CommandException(Protocol.E_TIMEOUT, "no matching frame within " + timeout + " ms", details);
                }
                stale = true;
            } catch (IllegalStateException e) {
                throw new CommandException(Protocol.E_NO_DISPLAY, "the display was released");
            }
            waitMs = (System.nanoTime() - waitStart) / 1e6;
            // 先选中满足边界的帧，再决定能否复用同一帧的编码结果。
            cached = key.equals(session.cacheKey) && session.cacheSeq == captured.seq;
            if (!cached) {
                int needed = width * height * channels;
                if (session.pixels == null || session.pixels.length < needed) {
                    session.pixels = new byte[needed];
                }
                long copyStart = System.nanoTime();
                current.copyLatest(x, y, width, height, channels, session.pixels);
                copyMs = (System.nanoTime() - copyStart) / 1e6;
            }
        }
        double encodeMs = 0;
        if (!cached) {
            long encodeStart = System.nanoTime();
            FrameEncoder.Encoded encoded = FrameEncoder.encode(session.pixels, width, height, options, encodePool(options.chunks));
            encodeMs = (System.nanoTime() - encodeStart) / 1e6;
            session.cacheHeader = frameHeader(current, captured, x, y, width, height, options, encoded);
            session.cacheKey = key;
            session.cacheSeq = captured.seq;
            session.cachePayload = encoded.data;
            session.cacheLength = encoded.length;
        }
        JSONObject header = new JSONObject(session.cacheHeader.toString());
        if (request.has("id")) {
            header.put("id", request.get("id"));
        }
        header.put("cached", cached);
        header.put("stale", stale);
        header.put("age_ms", SystemClock.elapsedRealtime() - captured.acquiredMs);
        header.put("wait_ms", waitMs);
        header.put("copy_ms", copyMs);
        header.put("encode_ms", encodeMs);
        return new Message(header, session.cachePayload, 0, session.cacheLength);
    }

    private static JSONObject frameHeader(VirtualScreen current, FrameSequencer.Frame captured,
                                          int x, int y, int width, int height,
                                          FrameEncoder.Options options, FrameEncoder.Encoded encoded) throws JSONException {
        JSONObject header = new JSONObject();
        header.put("ok", true);
        header.put("seq", captured.seq);
        header.put("display_id", current.displayId);
        header.put("width", width);
        header.put("height", height);
        header.put("channels", options.channels());
        header.put("encoding", options.encoding);
        header.put("crop", new JSONArray().put(x).put(y).put(width).put(height));
        header.put("image_ns", captured.imageNs);
        header.put("captured_ms", captured.acquiredMs);
        header.put("acquired_ns", captured.acquiredNs);
        header.put("timestamp_comparable", captured.timestampComparable);
        header.put("size", encoded.length);
        if (options.compressed()) {
            header.put("level", options.level);
            header.put("predictor", options.predictor);
            JSONArray lengths = new JSONArray();
            JSONArray rows = new JSONArray();
            for (int i = 0; i < encoded.chunkLengths.length; i++) {
                lengths.put(encoded.chunkLengths[i]);
                rows.put(encoded.chunkRows[i]);
            }
            header.put("chunks", lengths);
            header.put("chunk_rows", rows);
        }
        return header;
    }

    private synchronized ExecutorService encodePool(int chunks) {
        if (chunks <= 1) {
            return null;
        }
        if (encodePool == null) {
            int threads = Math.max(2, Math.min(4, Runtime.getRuntime().availableProcessors()));
            AtomicInteger counter = new AtomicInteger();
            encodePool = Executors.newFixedThreadPool(threads, runnable -> {
                Thread thread = new Thread(runnable, "m7a-encode-" + counter.incrementAndGet());
                thread.setDaemon(true);
                return thread;
            });
        }
        return encodePool;
    }

    // ---- 输入 ----

    /**
     * 注入前的检查。系统休眠或锁屏时注入“成功”但游戏收不到，这里直接报错，让客户端停下来。
     * 请求带 force=true 时跳过。
     */
    private void checkInjectable(JSONObject request, int displayId) throws CommandException {
        if (request.optBoolean("force", false)) {
            return;
        }
        VirtualScreen current = screen;
        boolean ownDisplay = current != null && current.displayId == displayId;
        try {
            if (!SystemApis.interactive()) {
                throw new CommandException(Protocol.E_DEVICE_ASLEEP, "the device is asleep; touches would not reach the game");
            }
            // Android 13 起我们的虚拟屏带 ALWAYS_UNLOCKED，不受锁屏影响
            boolean keyguardApplies = !(ownDisplay && Build.VERSION.SDK_INT >= 33);
            if (keyguardApplies && SystemApis.keyguardLocked()) {
                throw new CommandException(Protocol.E_KEYGUARD_LOCKED, "the keyguard is showing");
            }
        } catch (ReflectiveOperationException | RuntimeException e) {
            Logger.w("cannot read power state before injecting", e);
        }
        Watchdog dog = watchdog;
        if (dog != null) {
            dog.checkInput(displayId, ownDisplay);
        }
    }

    private static int pointerId(JSONObject request) {
        return request.has("pointer_id")
                ? JsonIntegers.id(request.opt("pointer_id"), "pointer_id", InputInjector.MAX_POINTERS - 1) : 0;
    }

    private JSONObject inputResult(JSONObject request, int displayId, boolean delivered) throws JSONException {
        long inputNs = System.nanoTime();
        JSONObject out = Message.ok(request);
        // 序号是发布进度，严格取帧使用 input_ns，避免跳过在组装回执期间发布的帧。
        out.put("seq", sequencer.latest());
        out.put("input_ns", inputNs);
        out.put("display_id", displayId);
        out.put("delivered", delivered);
        out.put("device_ms", SystemClock.elapsedRealtime());
        return out;
    }

    private JSONObject tap(Session session, JSONObject request) throws CommandException, JSONException, InterruptedException {
        int displayId = targetDisplay(request);
        float x = (float) request.getDouble("x");
        float y = (float) request.getDouble("y");
        int duration = clamp(request.optInt("duration_ms", DEFAULT_TAP_MS), 0, 10000);
        int pointer = pointerId(request);
        checkInjectable(request, displayId);
        long downSeq = sequencer.latest();
        boolean delivered = injector.tap(displayId, pointer, x, y, duration, session.id);
        JSONObject out = inputResult(request, displayId, delivered);
        out.put("down_seq", downSeq);
        return out;
    }

    private JSONObject swipe(Session session, JSONObject request) throws CommandException, JSONException, InterruptedException {
        int displayId = targetDisplay(request);
        JSONArray points = request.getJSONArray("points");
        if (points.length() < 2 || points.length() > 256) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "points must hold 2..256 [x, y] pairs");
        }
        float[] xs = new float[points.length()];
        float[] ys = new float[points.length()];
        for (int i = 0; i < xs.length; i++) {
            JSONArray point = points.getJSONArray(i);
            xs[i] = (float) point.getDouble(0);
            ys[i] = (float) point.getDouble(1);
        }
        int duration = clamp(request.optInt("duration_ms", 300), 0, 60000);
        int holdStart = clamp(request.optInt("hold_start_ms", 0), 0, 10000);
        int holdEnd = clamp(request.optInt("hold_end_ms", 0), 0, 10000);
        int pointer = pointerId(request);
        checkInjectable(request, displayId);
        long downSeq = sequencer.latest();
        boolean delivered = injector.swipe(displayId, pointer, new TouchPath(xs, ys), duration, holdStart, holdEnd, session.id);
        JSONObject out = inputResult(request, displayId, delivered);
        out.put("down_seq", downSeq);
        return out;
    }

    private JSONObject touch(Session session, JSONObject request) throws CommandException, JSONException {
        int displayId = targetDisplay(request);
        String action = request.optString("action", "");
        int pointer = pointerId(request);
        int code;
        switch (action) {
            case "down":
                code = MotionEvent.ACTION_DOWN;
                checkInjectable(request, displayId);
                break;
            case "move":
                code = MotionEvent.ACTION_MOVE;
                break;
            case "up":
                code = MotionEvent.ACTION_UP;
                break;
            default:
                throw new CommandException(Protocol.E_BAD_REQUEST, "action must be down, move or up");
        }
        float x;
        float y;
        if (code == MotionEvent.ACTION_UP && !request.has("x")) {
            // 抬起时可以不给坐标，沿用最后的位置
            x = Float.NaN;
            y = Float.NaN;
        } else {
            x = (float) request.getDouble("x");
            y = (float) request.getDouble("y");
        }
        boolean delivered = injector.touch(displayId, code, pointer, x, y, session.id);
        return inputResult(request, displayId, delivered);
    }

    private JSONObject key(JSONObject request) throws CommandException, JSONException {
        int displayId = targetDisplay(request);
        Object raw = request.opt("keycode");
        int code;
        if (raw instanceof Number) {
            code = ((Number) raw).intValue();
        } else if (raw instanceof String) {
            switch (((String) raw).toUpperCase(java.util.Locale.ROOT)) {
                case "BACK":
                    code = KeyEvent.KEYCODE_BACK;
                    break;
                case "ENTER":
                    code = KeyEvent.KEYCODE_ENTER;
                    break;
                case "ESCAPE":
                    code = KeyEvent.KEYCODE_ESCAPE;
                    break;
                case "DEL":
                    code = KeyEvent.KEYCODE_DEL;
                    break;
                default:
                    code = -1;
            }
        } else {
            code = -1;
        }
        // 只开放不会离开游戏、也不会改动系统状态的几个键
        if (code != KeyEvent.KEYCODE_BACK && code != KeyEvent.KEYCODE_ENTER
                && code != KeyEvent.KEYCODE_ESCAPE && code != KeyEvent.KEYCODE_DEL) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "keycode must be BACK, ENTER, ESCAPE or DEL");
        }
        checkInjectable(request, displayId);
        boolean delivered = injector.key(displayId, code);
        JSONObject out = inputResult(request, displayId, delivered);
        out.put("keycode", code);
        return out;
    }

    private JSONObject focus(JSONObject request) throws CommandException, JSONException {
        int displayId = targetDisplay(request);
        float x = (float) request.optDouble("x", 1);
        float y = (float) request.optDouble("y", 1);
        checkInjectable(request, displayId);
        boolean delivered = injector.focus(displayId, x, y);
        return inputResult(request, displayId, delivered);
    }

    // ---- 看门狗与事件 ----

    private JSONObject configureWatchdog(Session session, JSONObject request) throws CommandException, JSONException {
        JSONObject out = Message.ok(request);
        Watchdog previous;
        Watchdog next = null;
        synchronized (displayLock) {
            if (closed) {
                throw new CommandException(Protocol.E_INTERNAL, "service is closing");
            }
            if (request.optBoolean("enabled", true)) {
                JSONObject effective = request;
                if (request.isNull("main_activity") && lastLaunched != null
                        && lastLaunched.startsWith(request.optString("package", "") + "/")) {
                    // 也接受配置看门狗之前成功启动的同包组件。
                    effective = new JSONObject(request.toString());
                    effective.put("main_activity", lastLaunched.substring(lastLaunched.indexOf('/') + 1));
                }
                Watchdog.Config config = Watchdog.Config.fromJson(effective);
                try {
                    next = new Watchdog(config, this);
                } catch (IllegalArgumentException e) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, e.getMessage());
                }
            }
            previous = watchdog;
            watchdog = next;
        }
        if (previous != null) {
            previous.stop();
        }
        if (next != null) {
            if (request.optBoolean("subscribe", true)) {
                session.subscribed = true;
            }
            next.start();
            out.put("watchdog", next.describe());
        } else {
            out.put("watchdog", new JSONObject().put("enabled", false));
        }
        return out;
    }

    private JSONObject events(Session session, JSONObject request) throws JSONException {
        if (request.has("subscribe")) {
            session.subscribed = request.optBoolean("subscribe", false);
        }
        long after = request.optLong("after", 0);
        JSONObject out = Message.ok(request);
        JSONArray array = new JSONArray();
        synchronized (eventLog) {
            for (JSONObject event : eventLog) {
                if (event.optLong("event_seq") > after) {
                    array.put(event);
                }
            }
            out.put("event_seq", eventSeq);
        }
        out.put("events", array);
        out.put("subscribed", session.subscribed);
        return out;
    }

    @Override
    public void emit(String type, JSONObject fields) {
        Logger.i("watchdog event " + type + " " + fields);
        JSONObject event = new JSONObject();
        try {
            synchronized (eventLog) {
                eventSeq++;
                event.put("event", type);
                event.put("event_seq", eventSeq);
                event.put("time_ms", System.currentTimeMillis());
                event.put("device_ms", SystemClock.elapsedRealtime());
                event.put("frame_seq", sequencer.latest());
                Iterator<String> keys = fields.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    if (!event.has(key)) {
                        event.put(key, fields.get(key));
                    }
                }
                eventLog.addLast(event);
                while (eventLog.size() > EVENT_LOG_SIZE) {
                    eventLog.removeFirst();
                }
            }
        } catch (JSONException e) {
            Logger.w("cannot build event " + type, e);
            return;
        }
        for (Session session : sessions) {
            if (session.subscribed && session.sink != null) {
                try {
                    session.sink.onEvent(event);
                } catch (RuntimeException e) {
                    Logger.w("event sink of session " + session.id + " failed", e);
                }
            }
        }
    }

    @Override
    public boolean focusDisplay(int displayId) throws CommandException {
        return injector.focus(displayId, 1, 1);
    }

    @Override
    public int currentDisplayId() {
        VirtualScreen current = screen;
        return current == null ? -1 : current.displayId;
    }

    @Override
    public FrameSequencer.Frame latestFrame(int displayId) {
        VirtualScreen current = screen;
        return current == null || current.displayId != displayId ? null : current.latestFrame();
    }

    @Override
    public long latestSeq() {
        return sequencer.latest();
    }

    // ---- 面板与静音 ----

    private JSONObject screenPower(JSONObject request) throws CommandException, JSONException {
        if (!request.has("on")) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "on is required");
        }
        sideEffects.setPanel(request.getBoolean("on"));
        JSONObject out = Message.ok(request);
        out.put("panel_off", sideEffects.panelOff());
        return out;
    }

    private JSONObject mute(JSONObject request) throws CommandException, JSONException, InterruptedException {
        String packageName = request.optString("package", "");
        if (!PACKAGE.matcher(packageName).matches() || !request.has("on")) {
            throw new CommandException(Protocol.E_BAD_REQUEST, "package and on are required");
        }
        boolean on = request.getBoolean("on");
        String original = sideEffects.mute(packageName, on);
        JSONObject out = Message.ok(request);
        out.put("muted", sideEffects.mutedPackages().contains(packageName) || (on && "ignore".equals(original)));
        out.put("original_mode", original);
        return out;
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }
}
