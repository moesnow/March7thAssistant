package org.march7th.deviceservice.core;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.function.BooleanSupplier;
import java.util.Arrays;
import java.util.List;

/** 启动和运行共用恢复状态；一次持续故障不重发，恢复后才允许处理下一次故障。 */
final class DisplayFocusRecovery {
    static final long COOLDOWN_MS = 10000;
    private static final List<String> DEFERRED = Arrays.asList("picture_resumed", "context_changed", "task_changed", "sdk_window",
            "device_unavailable", "focus_changed", "active_gesture", "stopped");
    interface Host {
        long now();
        /** null 表示游戏、设备与服务均仍可操作。 */
        String contextProblem() throws Exception;
        boolean pictureStillBad(String reason) throws Exception;
        JSONObject evidence() throws Exception;
        /** allowed 必须在拿到输入锁后、真正发送 DOWN 前再次执行。 */
        JSONObject inject(BooleanSupplier allowed) throws Exception;
        default long frameSequence() { return -1; }
        /** 只有看门狗确认的另一轮任务回迁才会改变；客户端不能自行生成。 */
        default long moveGeneration() { return 0; }
        default boolean emulator() { return false; }
    }

    private boolean used;
    private Pending pending;
    private long lastAttemptMs;
    private long attemptedSeq;
    private long attemptedMove;
    private String attemptedReason;
    private boolean recovered;
    private boolean healthyConfirmed;
    private long episodeStartedMs;
    private long healthySince = -1;
    private long healthySeq = -1;
    private long lastObservation = -1;
    private int healthySamples;
    private long attemptId;

    /** 仅消费服务自己采集的帧，不接受客户端声称已经恢复。 */
    synchronized void observe(long now, long seq, long ageMs, Boolean black, boolean usable) {
        boolean fresh = usable && ageMs >= 0 && ageMs <= 3000 && seq > attemptedSeq;
        if (!used) return;
        if (("frame_timeout".equals(attemptedReason) || "move_back".equals(attemptedReason)) && fresh) recovered = true;
        if (!fresh || black != Boolean.FALSE || (lastObservation >= 0 && now - lastObservation > 8000)) {
            healthySince = -1;
            healthySamples = 0;
        }
        if (fresh && black == Boolean.FALSE && seq != healthySeq) {
            if (healthySince < 0) healthySince = now;
            healthySeq = seq;
            healthySamples++;
            if (now - healthySince >= 6000 && healthySamples >= 3) {
                recovered = true;
                healthyConfirmed = true;
            }
        }
        lastObservation = now;
    }

    private static final class Pending {
        final Host host;
        final JSONObject report;
        final long deadline;
        final int owner;

        Pending(Host host, JSONObject report, long deadline, int owner) {
            this.host = host;
            this.report = report;
            this.deadline = deadline;
            this.owner = owner;
        }
    }

    JSONObject prepare(Host host, String reason, int timeoutMs, long taskDeadline, int owner) throws JSONException {
        long deadline = Math.min(taskDeadline, host.now() + Math.max(1, Math.min(15000, timeoutMs)));
        JSONObject out = new JSONObject().put("reason", reason).put("attempted", false).put("deadline_ms", deadline);
        synchronized (this) {
            boolean newMove = "move_back".equals(reason) && host.moveGeneration() > attemptedMove;
            if (used && !newMove && (!recovered || host.now() - lastAttemptMs < COOLDOWN_MS)) {
                return out.put("status", "already_attempted");
            }
            if (used && !newMove && !healthyConfirmed && host.now() - episodeStartedMs >= 45000) {
                return out.put("status", "unrecovered");
            }
            if (!used || newMove || healthyConfirmed) episodeStartedMs = host.now();
            used = true;
            pending = null;
            recovered = false;
            healthyConfirmed = false;
            lastAttemptMs = host.now();
            attemptedSeq = host.frameSequence();
            attemptedMove = Math.max(attemptedMove, host.moveGeneration());
            attemptedReason = reason;
            healthySince = -1;
            healthySeq = -1;
            healthySamples = 0;
            out.put("attempt_id", ++attemptId);
        }
        try {
            String blocked = blockReason(host, reason, deadline);
            if (blocked != null) return out.put("status", blocked);
            JSONObject before = host.evidence();
            out.put("before", before);
            blocked = blockReason(host, reason, deadline);
            if (blocked != null) return out.put("status", blocked);
            String focus = before.optString("target_window_focus", "unknown");
            if (!"none".equals(focus) && !(host.emulator() && "game".equals(focus))) {
                return out.put("status", "focus_" + focus);
            }
            synchronized (this) {
                if (out.optLong("attempt_id") != attemptId) return out.put("status", "superseded");
                pending = new Pending(host, out, deadline, owner);
            }
            return out.put("status", "prepared");
        } catch (Exception error) {
            if (error instanceof InterruptedException) Thread.currentThread().interrupt();
            return out.put("status", error instanceof InterruptedException ? "stopped" : "unavailable")
                    .put("error", Logger.describe(error));
        } finally {
            releaseDeferred(out);
        }
    }

    JSONObject apply(int owner, long expectedAttempt) throws JSONException {
        Pending operation;
        synchronized (this) {
            operation = pending;
            if (operation == null || operation.owner != owner
                    || operation.report.optLong("attempt_id") != expectedAttempt) {
                return new JSONObject().put("attempted", false).put("status", "not_prepared");
            }
            pending = null; // 发送前取走，迟到回执、重复请求和另一连接都不能重放。
        }
        Host host = operation.host;
        JSONObject out = operation.report;
        String reason = out.getString("reason");
        long deadline = operation.deadline;
        String[] blocked = {null};
        BooleanSupplier allowed = () -> {
            try {
                blocked[0] = blockReason(host, reason, deadline);
            } catch (Exception error) {
                if (error instanceof InterruptedException) Thread.currentThread().interrupt();
                blocked[0] = error instanceof InterruptedException ? "stopped" : host.now() >= deadline ? "deadline" : "unavailable";
                try { out.put("guard_error", Logger.describe(error)); } catch (JSONException ignored) {}
            }
            return blocked[0] == null;
        };
        try {
            if (!allowed.getAsBoolean()) return out.put("status", blocked[0]);
            JSONObject before = out.getJSONObject("before");
            JSONObject injection = host.inject(allowed);
            boolean attempted = injection.optBoolean("attempted");
            out.put("attempted", attempted).put("injection", injection);
            String status = attempted ? "requested" : blocked[0];
            if (status == null) status = "active_gesture".equals(injection.optString("skipped")) ? "active_gesture" : "focus_changed";
            out.put("status", status);
            if (host.now() < deadline && !Thread.currentThread().isInterrupted() && host.contextProblem() == null) {
                JSONObject after = host.evidence();
                out.put("after", after);
                String observed = after.optString("target_window_focus", "unknown");
                out.put("focus_acquired", "unknown".equals(observed) ? JSONObject.NULL : "game".equals(observed));
                // 这是即时诊断；客户端继续观察后续帧，不能把回执当作画面恢复。
                out.put("frame_seq_before", before.optJSONObject("frame") == null ? -1 : before.getJSONObject("frame").optLong("seq", -1));
                out.put("frame_seq_after", after.optJSONObject("frame") == null ? -1 : after.getJSONObject("frame").optLong("seq", -1));
            }
        } catch (Exception error) {
            if (error instanceof InterruptedException) Thread.currentThread().interrupt();
            out.put("status", out.optBoolean("attempted") ? "requested" : "unavailable");
            out.put("error", Logger.describe(error));
        } finally {
            releaseDeferred(out);
        }
        return out;
    }

    private synchronized void releaseDeferred(JSONObject report) {
        if (report.optLong("attempt_id") == attemptId && !report.optBoolean("attempted")
                && DEFERRED.contains(report.optString("status"))) {
            used = false;
            pending = null;
        }
    }

    private String blockReason(Host host, String reason, long deadline) throws Exception {
        if (Thread.currentThread().isInterrupted()) return "stopped";
        if (host.now() >= deadline) return "deadline";
        String problem = host.contextProblem();
        if (problem != null) return problem;
        if (!host.pictureStillBad(reason)) return "picture_resumed";
        if (Thread.currentThread().isInterrupted()) return "stopped";
        problem = host.contextProblem();
        if (problem != null) return problem;
        // 上面的系统查询和像素复核也消耗本轮时间，不得在过期后下发 DOWN。
        return host.now() >= deadline ? "deadline" : null;
    }
}
