package org.march7th.deviceservice.core;

import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;
import org.march7th.deviceservice.protocol.FrameSequencer;
import org.march7th.deviceservice.protocol.JsonIntegers;
import org.march7th.deviceservice.protocol.Protocol;
import org.march7th.deviceservice.protocol.StackEntry;

import java.util.List;

/**
 * 回迁看门狗。
 *
 * 周期性地看四样东西：游戏进程、游戏任务在哪块屏、任务顶上是不是游戏主界面、目标屏有没有新帧。
 * 登录 SDK 会把整个游戏任务带到实体屏：等 SDK 窗口结束、主界面回到任务顶上并连续确认几次之后，
 * 才把任务移回目标屏，并等到移回之后的新帧。SDK 窗口一直不走（需要人工登录）时只上报，不和用户抢。
 */
final class Watchdog {
    static final class Config {
        String packageName;
        /** 游戏主 Activity 的完整类名。任务顶上是别的 Activity 时一律当作 SDK 窗口。 */
        String mainActivity;
        /** 目标屏；-1 表示跟随当前的虚拟屏。 */
        int displayId = -1;
        int intervalMs = 500;
        boolean autoMoveBack = true;
        /** 连续多少次检查都满足条件才回迁。 */
        int settlePolls = 2;
        int manualTimeoutMs = 15000;
        int moveTimeoutMs = 5000;
        int maxMoveAttempts = 3;
        /** 目标屏多久没有新帧算停止出帧；0 表示不检查。 */
        int stallMs = 10000;
        String inspector = TaskInspector.AUTO;
        /** 任务移回后、以及目标屏停止出帧时，是否自动把焦点切到目标屏。 */
        boolean autoFocus;
        /** 游戏进程退出后是否自动在目标屏重新启动。 */
        boolean relaunch;
        int maxRelaunches = 2;
        /** 重新启动用的组件名，形如 包名/类名。 */
        String component;

        static Config fromJson(JSONObject request) throws CommandException {
            Config config = new Config();
            config.packageName = request.optString("package", null);
            if (config.packageName == null || !config.packageName.matches("[A-Za-z0-9_.]+")) {
                throw new CommandException(Protocol.E_BAD_REQUEST, "package is required");
            }
            config.mainActivity = request.optString("main_activity", null);
            if (config.mainActivity != null && config.mainActivity.startsWith(".")) {
                config.mainActivity = config.packageName + config.mainActivity;
            }
            if (request.has("display_id")) {
                config.displayId = JsonIntegers.id(request.opt("display_id"), "display_id", Integer.MAX_VALUE);
            }
            config.intervalMs = clamp(request.optInt("interval_ms", 500), 100, 60000);
            config.autoMoveBack = request.optBoolean("auto_move_back", true);
            config.settlePolls = clamp(request.optInt("settle_polls", 2), 1, 20);
            config.manualTimeoutMs = clamp(request.optInt("manual_timeout_ms", 15000), 1000, 600000);
            config.moveTimeoutMs = clamp(request.optInt("move_timeout_ms", 5000), 500, 60000);
            config.maxMoveAttempts = clamp(request.optInt("max_move_attempts", 3), 1, 20);
            config.stallMs = clamp(request.optInt("stall_ms", 10000), 0, 600000);
            config.inspector = request.optString("inspector", TaskInspector.AUTO);
            config.autoFocus = request.optBoolean("auto_focus", false);
            config.relaunch = request.optBoolean("relaunch", false);
            config.maxRelaunches = clamp(request.optInt("max_relaunches", 2), 0, 10);
            if (config.relaunch) {
                if (config.mainActivity == null) {
                    throw new CommandException(Protocol.E_BAD_REQUEST, "relaunch needs main_activity");
                }
                config.component = config.packageName + "/" + config.mainActivity;
            }
            return config;
        }

        private static int clamp(int value, int min, int max) {
            return Math.max(min, Math.min(max, value));
        }
    }

    /** 看门狗需要服务提供的能力。 */
    interface Host {
        void emit(String type, JSONObject fields);

        /** 当前虚拟屏的 ID，没有时为 -1。 */
        int currentDisplayId();

        long latestSeq();

        /** 只返回指定屏的最新帧；还没有帧或不是当前虚拟屏时为 null。 */
        FrameSequencer.Frame latestFrame(int displayId);

        void launch(String component, int displayId) throws Exception;

        /** 让一块屏成为焦点屏，返回触摸是否送达。 */
        boolean focusDisplay(int displayId) throws Exception;
    }

    interface Platform {
        long elapsedMs();
        long nanoTime();
        boolean interactive() throws Exception;
        boolean keyguardLocked() throws Exception;
        String processName(int pid);
        int findProcess(String packageName);
        String inspectorMode();
        List<StackEntry> stacks() throws Exception;
        void move(int stackId, int displayId) throws Exception;
    }

    private static final class AndroidPlatform implements Platform {
        private final TaskInspector inspector;

        AndroidPlatform(String mode) {
            inspector = new TaskInspector(mode);
        }

        @Override
        public long elapsedMs() {
            return SystemClock.elapsedRealtime();
        }

        @Override
        public long nanoTime() {
            return System.nanoTime();
        }

        @Override
        public boolean interactive() throws Exception {
            return SystemApis.interactive();
        }

        @Override
        public boolean keyguardLocked() throws Exception {
            return SystemApis.keyguardLocked();
        }

        @Override
        public String processName(int pid) {
            return SystemApis.processName(pid);
        }

        @Override
        public int findProcess(String packageName) {
            return SystemApis.findProcess(packageName);
        }

        @Override
        public String inspectorMode() {
            return inspector.activeMode();
        }

        @Override
        public List<StackEntry> stacks() throws Exception {
            return inspector.stacks();
        }

        @Override
        public void move(int stackId, int displayId) throws Exception {
            inspector.move(stackId, displayId);
        }
    }

    private static final class PendingFrame {
        final StackEntry task;
        final int attempt;
        final long startedAt;
        final long deadline;
        long afterSeq;
        long afterNs;
        boolean waitingForMain;
        boolean timedOut;

        PendingFrame(StackEntry task, int attempt, long startedAt, long deadline, long afterSeq, long afterNs) {
            this.task = task;
            this.attempt = attempt;
            this.startedAt = startedAt;
            this.deadline = deadline;
            this.afterSeq = afterSeq;
            this.afterNs = afterNs;
        }
    }

    private final Config config;
    private final Host host;
    private final Platform platform;
    private final Thread thread;
    private volatile boolean running = true;

    // 以下状态只在看门狗线程里改，读取时加锁
    private final Object stateLock = new Object();
    private boolean primed;
    private int pid = -1;
    private long lastProcessScan;
    private StackEntry game;
    private boolean interactive = true;
    private boolean keyguardLocked;
    private String foreignActivity;
    private long foreignSince;
    private boolean manualNotified;
    private int settled;
    private int moveAttempts;
    private boolean moveGaveUp;
    private PendingFrame pendingFrame;
    private long mainOnTargetSince = -1;
    private boolean stalled;
    private boolean everRunning;
    private int relaunches;
    private boolean recoveryFailed;
    private long lastErrorAt;

    Watchdog(Config config, Host host) {
        this(config, host, new AndroidPlatform(config.inspector));
    }

    Watchdog(Config config, Host host, Platform platform) {
        this.config = config;
        this.host = host;
        this.platform = platform;
        thread = new Thread(this::loop, "m7a-watchdog");
        thread.setDaemon(true);
    }

    void start() {
        thread.start();
    }

    void stop() {
        running = false;
        thread.interrupt();
        try {
            thread.join(3000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private int targetDisplay() {
        return config.displayId >= 0 ? config.displayId : host.currentDisplayId();
    }

    /** 普通客户端输入和自动切焦点都以最近一次观测到的任务栈顶为准。 */
    void checkInput(int displayId, boolean ownDisplay) throws CommandException {
        synchronized (stateLock) {
            if (!primed) {
                return;
            }
            if (game != null && game.displayId == displayId && isSdkWindow(game)) {
                throw new CommandException(Protocol.E_SDK_WINDOW_ACTIVE, "SDK activity is active: " + game.topActivity);
            }
            if (ownDisplay && (game == null || game.displayId != displayId)) {
                throw new CommandException(Protocol.E_GAME_NOT_ON_DISPLAY,
                        config.packageName + " is not on display " + displayId);
            }
        }
    }

    JSONObject describe() throws JSONException {
        JSONObject json = new JSONObject();
        synchronized (stateLock) {
            json.put("enabled", true);
            json.put("package", config.packageName);
            json.put("main_activity", config.mainActivity == null ? JSONObject.NULL : config.mainActivity);
            json.put("target_display_id", targetDisplay());
            json.put("inspector", platform.inspectorMode());
            json.put("auto_focus", config.autoFocus);
            json.put("pid", pid);
            json.put("interactive", interactive);
            json.put("keyguard_locked", keyguardLocked);
            if (game == null) {
                json.put("task", JSONObject.NULL);
            } else {
                JSONObject task = new JSONObject();
                task.put("stack_id", game.stackId);
                task.put("task_id", game.taskIdOf(config.packageName));
                task.put("display_id", game.displayId);
                task.put("visible", game.visible);
                task.put("top_activity", game.topActivity == null ? JSONObject.NULL : game.topActivity);
                json.put("task", task);
            }
            json.put("sdk_window", foreignActivity == null ? JSONObject.NULL : foreignActivity);
            json.put("move_attempts", moveAttempts);
            json.put("move_gave_up", moveGaveUp);
            json.put("frames_stalled", stalled);
        }
        return json;
    }

    private void loop() {
        Logger.i("watchdog started for " + config.packageName + " target display " + targetDisplay());
        while (running) {
            try {
                poll();
            } catch (InterruptedException e) {
                break;
            } catch (Throwable error) {
                long now = platform.elapsedMs();
                if (now - lastErrorAt > 10000) {
                    lastErrorAt = now;
                    Logger.w("watchdog poll failed", error);
                    emit("watchdog_error", fields("message", Logger.describe(error)));
                }
            }
            try {
                int interval = TaskInspector.SHELL.equals(platform.inspectorMode())
                        ? Math.max(config.intervalMs, 1000) : config.intervalMs;
                Thread.sleep(interval);
            } catch (InterruptedException e) {
                break;
            }
        }
        Logger.i("watchdog stopped");
    }

    private StackEntry findGame(List<StackEntry> stacks) {
        StackEntry fallback = null;
        for (StackEntry entry : stacks) {
            if (!entry.belongsTo(config.packageName)) {
                continue;
            }
            if (entry.topActivity != null) {
                return entry;
            }
            if (fallback == null) {
                fallback = entry;
            }
        }
        return fallback;
    }

    private int trackProcess(boolean hasTask) {
        if (pid > 0 && config.packageName.equals(platform.processName(pid))) {
            return pid;
        }
        // 全量扫描 /proc 比较贵：有任务或者刚丢失进程时每次都扫，否则两秒扫一次
        long now = platform.elapsedMs();
        if (pid <= 0 && !hasTask && now - lastProcessScan < 2000) {
            return -1;
        }
        lastProcessScan = now;
        return platform.findProcess(config.packageName);
    }

    private boolean isMain(StackEntry entry) {
        if (entry.topActivity == null) {
            return false;
        }
        if (!entry.topActivity.startsWith(config.packageName + "/")) {
            return false;
        }
        return config.mainActivity == null || config.mainActivity.equals(entry.topActivityClass());
    }

    private boolean isSdkWindow(StackEntry entry) {
        return entry != null && entry.topActivity != null && !isMain(entry);
    }

    void poll() throws Exception {
        StackEntry current = findGame(platform.stacks());
        int currentPid = trackProcess(current != null);
        boolean nowInteractive = platform.interactive();
        boolean nowKeyguard = platform.keyguardLocked();
        boolean usable = nowInteractive && !nowKeyguard;
        long now = platform.elapsedMs();
        int target = targetDisplay();

        if (!primed) {
            synchronized (stateLock) {
                game = current;
                pid = currentPid;
                interactive = nowInteractive;
                keyguardLocked = nowKeyguard;
                everRunning = currentPid > 0;
                if (isSdkWindow(current)) {
                    foreignActivity = current.topActivity;
                    foreignSince = now;
                }
                primed = true;
            }
            emit("watchdog_started", describe());
            return;
        }

        StackEntry previousGame;
        synchronized (stateLock) {
            previousGame = game;
            game = current;
        }
        if (nowInteractive != interactive || nowKeyguard != keyguardLocked) {
            synchronized (stateLock) {
                interactive = nowInteractive;
                keyguardLocked = nowKeyguard;
            }
            emit("device_state", fields("interactive", nowInteractive, "keyguard_locked", nowKeyguard));
        }

        if (currentPid != pid) {
            int previous = pid;
            synchronized (stateLock) {
                pid = currentPid;
            }
            if (previous > 0) {
                emit("game_exited", fields("pid", previous));
            }
            if (currentPid > 0) {
                everRunning = true;
                recoveryFailed = false;
                emit("game_started", fields("pid", currentPid));
            }
        }

        Integer previousDisplay = previousGame == null ? null : previousGame.displayId;
        Integer currentDisplay = current == null ? null : current.displayId;
        if (previousDisplay == null ? currentDisplay != null : !previousDisplay.equals(currentDisplay)) {
            StackEntry reference = current != null ? current : previousGame;
            emit("task_display_changed", fields(
                    "from", previousDisplay == null ? JSONObject.NULL : previousDisplay,
                    "to", currentDisplay == null ? JSONObject.NULL : currentDisplay,
                    "stack_id", reference.stackId,
                    "task_id", reference.taskIdOf(config.packageName),
                    "target_display_id", target));
            moveAttempts = 0;
            moveGaveUp = false;
            settled = 0;
        }

        String foreign = isSdkWindow(current) ? current.topActivity : null;
        if (foreign == null ? foreignActivity != null : !foreign.equals(foreignActivity)) {
            if (foreignActivity != null) {
                emit("sdk_window_gone", fields("activity", foreignActivity, "duration_ms", now - foreignSince));
            }
            synchronized (stateLock) {
                foreignActivity = foreign;
            }
            foreignSince = now;
            manualNotified = false;
            if (foreign != null) {
                emit("sdk_window_shown", fields("activity", foreign, "display_id", current.displayId));
            }
        }
        if (foreign != null && !manualNotified && now - foreignSince >= config.manualTimeoutMs) {
            manualNotified = true;
            emit("manual_action_required", fields("activity", foreign, "display_id", current.displayId,
                    "waited_ms", now - foreignSince));
        }

        checkMoveFrame(current, target, usable);
        boolean misplaced = current != null && target >= 0 && current.displayId != target;
        if (misplaced && config.autoMoveBack && !moveGaveUp) {
            if (foreign == null && isMain(current)) {
                settled++;
                if (settled >= config.settlePolls) {
                    settled = 0;
                    moveBack(current, target, usable);
                    current = game;
                }
            } else {
                settled = 0;
            }
        } else {
            settled = 0;
        }

        checkStall(current, target, usable, platform.elapsedMs());
        checkRelaunch(current, currentPid, target);
    }

    private void moveBack(StackEntry entry, int target, boolean usable) throws InterruptedException {
        moveAttempts++;
        long startedAt = platform.elapsedMs();
        int attempt = moveAttempts;
        emit("move_back_started", fields("stack_id", entry.stackId, "from", entry.displayId, "to", target, "attempt", attempt));
        String failure = null;
        StackEntry moved = null;
        try {
            platform.move(entry.stackId, target);
            long deadline = startedAt + config.moveTimeoutMs;
            while (platform.elapsedMs() < deadline) {
                StackEntry now = findGame(platform.stacks());
                if (now != null && now.displayId == target) {
                    moved = now;
                    break;
                }
                Thread.sleep(100);
            }
            if (moved == null) {
                failure = "task did not reach display " + target;
            }
        } catch (InterruptedException e) {
            throw e;
        } catch (Exception e) {
            failure = "move failed: " + Logger.describe(e);
        }
        if (failure != null) {
            boolean last = attempt >= config.maxMoveAttempts;
            moveGaveUp = last;
            emit("move_back_failed", fields("reason", failure, "attempt", attempt, "final", last,
                    "elapsed_ms", platform.elapsedMs() - startedAt));
            return;
        }
        synchronized (stateLock) {
            game = moved;
        }
        long arrivalNs = platform.nanoTime();
        long arrivalSeq = host.latestSeq();
        long deadline = platform.elapsedMs() + config.moveTimeoutMs;
        emit("task_display_changed", fields("from", entry.displayId, "to", target, "stack_id", moved.stackId,
                "task_id", moved.taskIdOf(config.packageName), "target_display_id", target));
        if (target == host.currentDisplayId()) {
            pendingFrame = new PendingFrame(moved, attempt, startedAt, deadline, arrivalSeq, arrivalNs);
            requestFocus(moved, target, "move_back", usable);
            checkMoveFrame(moved, target, usable);
        } else {
            moveSucceeded(moved, attempt, startedAt, null, false);
        }
    }

    private void checkMoveFrame(StackEntry current, int target, boolean usable) {
        PendingFrame pending = pendingFrame;
        if (pending == null) {
            return;
        }
        if (target != pending.task.displayId || target != host.currentDisplayId()
                || current == null || current.displayId != target || current.stackId != pending.task.stackId
                || current.taskIdOf(config.packageName) != pending.task.taskIdOf(config.packageName)) {
            pendingFrame = null;
            return;
        }
        boolean main = isMain(current);
        if (pending.waitingForMain || !main) {
            // SDK 的画面不能充当主界面回迁成功的证据。
            pending.afterNs = platform.nanoTime();
            pending.afterSeq = host.latestSeq();
            if (main) {
                requestFocus(current, target, "move_back", usable);
            }
            pending.waitingForMain = !main;
        }
        FrameSequencer.Frame frame = host.latestFrame(target);
        if (main && usable && frame != null && frame.seq > pending.afterSeq
                && (!frame.timestampComparable || frame.isAfter(pending.afterNs))) {
            pendingFrame = null;
            moveSucceeded(current, pending.attempt, pending.startedAt, frame, pending.timedOut);
        } else if (!pending.timedOut && platform.elapsedMs() >= pending.deadline) {
            pending.timedOut = true;
            emit("move_back_frame_timeout", fields("stack_id", current.stackId, "task_id", current.taskIdOf(config.packageName),
                    "display_id", target, "attempt", pending.attempt, "elapsed_ms", platform.elapsedMs() - pending.startedAt));
        }
    }

    private void moveSucceeded(StackEntry moved, int attempt, long startedAt, FrameSequencer.Frame frame, boolean late) {
        moveAttempts = 0;
        emit("move_back_succeeded", fields("stack_id", moved.stackId, "task_id", moved.taskIdOf(config.packageName),
                "display_id", moved.displayId, "attempt", attempt, "elapsed_ms", platform.elapsedMs() - startedAt,
                "first_frame_seq", frame == null ? -1 : frame.seq, "late_frame", late,
                "frame_boundary", frame == null ? "none" : frame.timestampComparable ? "timestamp" : "sequence"));
    }

    private void checkStall(StackEntry current, int target, boolean usable, long now) {
        if (config.stallMs <= 0 || target < 0 || target != host.currentDisplayId() || !usable
                || current == null || current.displayId != target || !isMain(current)) {
            mainOnTargetSince = -1;
            synchronized (stateLock) {
                stalled = false;
            }
            return;
        }
        if (mainOnTargetSince < 0) {
            mainOnTargetSince = now;
        }
        FrameSequencer.Frame latest = host.latestFrame(target);
        long age = latest == null ? -1 : Math.max(0, now - latest.acquiredMs);
        boolean nowStalled = now - mainOnTargetSince >= config.stallMs && (latest == null || age >= config.stallMs);
        if (nowStalled != stalled) {
            synchronized (stateLock) {
                stalled = nowStalled;
            }
            emit(nowStalled ? "frames_stalled" : "frames_resumed", fields("age_ms", age, "display_id", target));
            if (nowStalled) {
                requestFocus(current, target, "frames_stalled", true);
            }
        }
    }

    /** 有的系统上游戏在没有焦点的屏里不渲染（MuMu 的 Android 12 如此），按配置把焦点切过去。 */
    private void requestFocus(StackEntry current, int target, String reason, boolean usable) {
        if (!running || !config.autoFocus || !usable || current.displayId != target
                || !isMain(current) || target != host.currentDisplayId()) {
            return;
        }
        try {
            boolean delivered = host.focusDisplay(target);
            emit("focus_requested", fields("display_id", target, "reason", reason, "delivered", delivered));
        } catch (Exception e) {
            emit("focus_requested", fields("display_id", target, "reason", reason, "delivered", false,
                    "error", Logger.describe(e)));
        }
    }

    private void checkRelaunch(StackEntry current, int currentPid, int target) {
        if (!config.relaunch || !everRunning || current != null || currentPid > 0 || target < 0 || recoveryFailed) {
            return;
        }
        if (relaunches >= config.maxRelaunches) {
            recoveryFailed = true;
            emit("recovery_failed", fields("reason", "game exited " + (relaunches + 1) + " times", "relaunches", relaunches));
            return;
        }
        relaunches++;
        try {
            host.launch(config.component, target);
            emit("relaunched", fields("attempt", relaunches, "display_id", target));
        } catch (Exception e) {
            emit("relaunch_failed", fields("attempt", relaunches, "reason", Logger.describe(e)));
        }
    }

    private void emit(String type, JSONObject fields) {
        host.emit(type, fields);
    }

    private static JSONObject fields(Object... pairs) {
        JSONObject json = new JSONObject();
        try {
            for (int i = 0; i < pairs.length; i += 2) {
                json.put((String) pairs[i], pairs[i + 1]);
            }
        } catch (JSONException e) {
            throw new IllegalStateException(e);
        }
        return json;
    }
}
