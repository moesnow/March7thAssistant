package org.march7th.deviceservice.core;

import org.json.JSONObject;
import org.junit.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.function.BooleanSupplier;
import static org.junit.Assert.*;

public class DisplayFocusRecoveryTest {
    @Test
    public void blackAndStalledFramesShareOneGestureAndKeepReceiptSeparateFromRecovery() throws Exception {
        for (String reason : List.of("frame_timeout", "virtual_display_black")) {
            for (boolean gainsFocus : new boolean[]{false, true}) {
                DisplayFocusRecovery recovery = new DisplayFocusRecovery();
                Host host = new Host();
                host.gainsFocus = gainsFocus;
                JSONObject result = recover(recovery, host, reason);
                assertEquals("requested", result.getString("status"));
                assertEquals(gainsFocus, result.getBoolean("focus_acquired"));
                assertTrue(result.getJSONObject("injection").getBoolean("down_accepted"));
                assertEquals(List.of("DOWN@130", "CANCEL@130"), host.actions);
                assertEquals(35, result.getLong("frame_seq_after")); // 送达甚至取得焦点都不能伪造一张新帧。
                for (int i = 0; i < 20; i++) {
                    assertEquals("already_attempted", recover(recovery, host, "virtual_display_black").getString("status"));
                }
                assertEquals(2, host.actions.size());
                assertEquals(2, host.evidenceReads);
            }
        }
    }

    @Test
    public void focusMustBeExplicitlyAbsent() throws Exception {
        for (String focus : List.of("game", "other", "unknown")) {
            Host host = new Host();
            host.focus = focus;
            JSONObject result = recover(new DisplayFocusRecovery(), host, "virtual_display_black");
            assertFalse(result.getBoolean("attempted"));
            assertEquals("focus_" + focus, result.getString("status"));
            assertTrue(host.actions.isEmpty());
        }
    }

    @Test
    public void rechecksTransitionsStopAndDeadlineAfterEvidenceAndInsideTheInputLock() throws Exception {
        for (String stage : List.of("evidence", "input_lock", "pixels")) {
            for (String fault : List.of("picture_resumed", "task_changed", "sdk_window", "device_unavailable", "stopped", "deadline")) {
                Host host = new Host();
                Runnable change = () -> {
                    if (fault.equals("picture_resumed")) host.bad = false;
                    else if (fault.equals("deadline")) host.time += 15001;
                    else host.problem = fault;
                };
                if (stage.equals("evidence")) host.beforeEvidence = change;
                else if (stage.equals("input_lock")) host.beforeInput = change;
                else host.duringPixels = change;
                JSONObject result = recover(new DisplayFocusRecovery(), host, "virtual_display_black");
                assertEquals(stage + ":" + fault, fault, result.getString("status"));
                assertFalse(result.getBoolean("attempted"));
                assertTrue(host.actions.isEmpty());
            }
        }
    }

    @Test
    public void aLostReceiptStillCancelsAndNeverResends() throws Exception {
        Host host = new Host();
        host.downError = true;
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        JSONObject result = recover(recovery, host, "frame_timeout");
        assertTrue(result.getBoolean("attempted"));
        assertTrue(result.getJSONObject("injection").getString("down_error").contains("inject_failed"));
        assertEquals(List.of("DOWN@130", "CANCEL@130"), host.actions);
        assertFalse(result.getBoolean("focus_acquired"));
        recover(recovery, host, "frame_timeout");
        assertEquals(2, host.actions.size());
    }

    @Test
    public void diagnosticFailureDoesNotIntroduceUnverifiedInputOrEraseAnAttempt() throws Exception {
        for (int failAt : new int[]{1, 2}) {
            Host host = new Host();
            host.failEvidenceAt = failAt;
            JSONObject result = recover(new DisplayFocusRecovery(), host, "virtual_display_black");
            assertEquals(failAt == 2, result.getBoolean("attempted"));
            assertEquals(failAt == 1 ? "unavailable" : "requested", result.getString("status"));
            assertEquals(failAt == 1 ? 0 : 2, host.actions.size());
            assertTrue(result.has("error"));
        }
    }

    @Test
    public void prepareNeverInjectsAndApplyCannotChangeOwnerReplayOrResetTheDeadline() throws Exception {
        Host host = new Host();
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        JSONObject prepared = recovery.prepare(host, "frame_timeout", 15000, host.now() + 2000, 7);
        assertEquals("prepared", prepared.getString("status"));
        assertTrue(host.actions.isEmpty());
        assertEquals("not_prepared", recovery.apply(8, 1).getString("status"));
        host.time += 2001;
        assertEquals("deadline", recovery.apply(7, 1).getString("status"));
        assertEquals("not_prepared", recovery.apply(7, 1).getString("status"));
        assertTrue(host.actions.isEmpty());
    }

    @Test
    public void stoppingBetweenRequestsAndFocusChangingInsideTheInputLockAreSafe() throws Exception {
        Host stopped = new Host();
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        recovery.prepare(stopped, "frame_timeout", 15000, stopped.now() + 15000, 7);
        stopped.problem = "stopped";
        assertEquals("stopped", recovery.apply(7, 1).getString("status"));
        assertTrue(stopped.actions.isEmpty());
        Host changed = new Host();
        changed.beforeInput = () -> changed.focus = "other";
        JSONObject result = recover(new DisplayFocusRecovery(), changed, "frame_timeout");
        assertFalse(result.getBoolean("attempted"));
        assertTrue(changed.actions.isEmpty());
    }

    @Test
    public void aContinuousFailureNeverRearmsJustBecauseTimePassed() throws Exception {
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        Host host = new Host();
        recover(recovery, host, "virtual_display_black");
        for (int i = 0; i < 100; i++) {
            host.time += 3000;
            recovery.observe(host.time, ++host.seq, 0, true, true);
            assertEquals("already_attempted", recover(recovery, host, "frame_timeout").getString("status"));
        }
        assertEquals(List.of("DOWN@130", "CANCEL@130"), host.actions);
    }

    @Test
    public void blackFramesNeedSeveralHealthySamplesAndThenCanRecoverAgain() throws Exception {
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        Host host = new Host();
        recover(recovery, host, "virtual_display_black");
        host.time += 11000;
        recovery.observe(host.time, ++host.seq, 0, false, true);
        assertEquals("already_attempted", recover(recovery, host, "virtual_display_black").getString("status"));
        host.time += 3000;
        recovery.observe(host.time, ++host.seq, 0, false, true);
        host.time += 3000;
        recovery.observe(host.time, ++host.seq, 0, false, true);
        assertEquals("requested", recover(recovery, host, "virtual_display_black").getString("status"));
        assertEquals(4, host.actions.size());
    }

    @Test
    public void aResumedStreamAndCooldownPermitTheNextStallButNotALostReceipt() throws Exception {
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        Host host = new Host();
        recover(recovery, host, "frame_timeout");
        host.time += 1000;
        recovery.observe(host.time, ++host.seq, 0, true, true);
        assertEquals("already_attempted", recover(recovery, host, "frame_timeout").getString("status"));
        host.time += DisplayFocusRecovery.COOLDOWN_MS;
        assertEquals("requested", recover(recovery, host, "frame_timeout").getString("status"));
        host.time += 60000;
        assertEquals("already_attempted", recover(recovery, host, "frame_timeout").getString("status"));
        assertEquals(4, host.actions.size());
    }

    @Test
    public void aNewConfirmedMoveSharesTheEngineButCannotReplayAnOldApply() throws Exception {
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        Host host = new Host();
        JSONObject first = recovery.prepare(host, "frame_timeout", 15000, host.now() + 15000, 7);
        assertEquals("prepared", first.getString("status"));
        host.move++;
        JSONObject next = recovery.prepare(host, "move_back", 15000, host.now() + 15000, 7);
        assertEquals("prepared", next.getString("status"));
        assertEquals("not_prepared", recovery.apply(7, first.getLong("attempt_id")).getString("status"));
        assertEquals("requested", recovery.apply(7, next.getLong("attempt_id")).getString("status"));
        assertEquals("already_attempted", recover(recovery, host, "move_back").getString("status"));
        assertEquals(2, host.actions.size());
    }

    @Test
    public void isolatedBlackBuffersCannotExtendTheRecoveryWindowForever() throws Exception {
        Host host = new Host();
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        recover(recovery, host, "frame_timeout");
        for (int i = 0; i < 20; i++) {
            host.time += 11000;
            recovery.observe(host.time, ++host.seq, 0, true, true);
            JSONObject result = recover(recovery, host, "frame_timeout");
            assertEquals(i < 4 ? "requested" : "unrecovered", result.getString("status"));
        }
        assertEquals(10, host.actions.size());
    }

    @Test
    public void aTemporaryLockWithoutAnyInputDoesNotUseTheNextRecoveryChance() throws Exception {
        Host host = new Host();
        host.problem = "device_unavailable";
        DisplayFocusRecovery recovery = new DisplayFocusRecovery();
        assertEquals("device_unavailable", recover(recovery, host, "frame_timeout").getString("status"));
        assertTrue(host.actions.isEmpty());
        host.problem = null;
        assertEquals("requested", recover(recovery, host, "frame_timeout").getString("status"));
        assertEquals(List.of("DOWN@130", "CANCEL@130"), host.actions);
    }

    @Test
    public void theEmulatorCanKeepItsGameFocusedButCannotStealAnotherWindow() throws Exception {
        for (String focus : List.of("none", "game", "other", "unknown")) {
            Host host = new Host();
            host.emulator = true;
            host.focus = focus;
            JSONObject report = recover(new DisplayFocusRecovery(), host, "move_back");
            assertEquals(focus, focus.equals("none") || focus.equals("game"), report.getBoolean("attempted"));
        }
    }

    private static JSONObject recover(DisplayFocusRecovery recovery, Host host, String reason) throws Exception {
        JSONObject prepared = recovery.prepare(host, reason, 15000, host.now() + 15000, 7);
        return "prepared".equals(prepared.optString("status")) ? recovery.apply(7, prepared.getLong("attempt_id")) : prepared;
    }

    private static final class Host implements DisplayFocusRecovery.Host {
        long time = 100000;
        long seq = 35;
        long move;
        boolean emulator;
        String focus = "none";
        String problem;
        boolean bad = true;
        boolean gainsFocus;
        boolean downError;
        int evidenceReads;
        int pixelReads;
        int failEvidenceAt;
        Runnable beforeEvidence = () -> {};
        Runnable beforeInput = () -> {};
        Runnable duringPixels = () -> {};
        final List<String> actions = new ArrayList<>();

        public long now() { return time; }
        public long frameSequence() { return seq; }
        public long moveGeneration() { return move; }
        public boolean emulator() { return emulator; }
        public String contextProblem() { return problem; }
        public boolean pictureStillBad(String reason) {
            if (++pixelReads == 3) duringPixels.run();
            return bad;
        }
        public JSONObject evidence() throws Exception {
            if (++evidenceReads == 1) beforeEvidence.run();
            if (evidenceReads == failEvidenceAt) throw new IllegalStateException("dump unavailable");
            return new JSONObject().put("target_window_focus", focus)
                    .put("frame", new JSONObject().put("seq", 35).put("age_ms", 11000));
        }
        public JSONObject inject(BooleanSupplier allowed) throws Exception {
            beforeInput.run();
            if (!allowed.getAsBoolean() || !("none".equals(focus) || (emulator && "game".equals(focus)))) {
                return FocusInjection.skipped("guard").describe();
            }
            return FocusInjection.send(() -> {
                actions.add("DOWN@130");
                if (downError) throw new CommandException("inject_failed", "late receipt");
                if (gainsFocus) focus = "game";
                return true;
            }, () -> { actions.add("CANCEL@130"); return true; }).describe();
        }
    }
}
