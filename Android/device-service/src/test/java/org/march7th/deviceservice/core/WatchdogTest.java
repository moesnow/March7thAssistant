package org.march7th.deviceservice.core;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

import org.json.JSONObject;
import org.junit.Test;
import org.march7th.deviceservice.protocol.FrameSequencer;
import org.march7th.deviceservice.protocol.Protocol;
import org.march7th.deviceservice.protocol.StackEntry;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BooleanSupplier;

public class WatchdogTest {
    private static final String PACKAGE = "example.game";
    private static final String MAIN = PACKAGE + ".Main";
    private static final String SDK = PACKAGE + "/.Login";
    private static final int TARGET = 42;

    @Test
    public void launchGuardReadsLiveTaskEvenWhenTheLastPollSawNone() throws Exception {
        Fixture platform = new Fixture();
        Watchdog.Config config = config();
        config.displayId = TARGET;
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        assertEquals(platform.now, dog.describe().getLong("task_checked_ms"));

        platform.setTask(0, PACKAGE + "/.Main");
        assertTrue(dog.hasGameTask(PACKAGE + "/.Main", TARGET));
        assertTrue(dog.describe().isNull("task"));
        assertThrows(CommandException.class, () -> dog.hasGameTask(PACKAGE + "/.Main", 0));

        platform.task = null;
        assertFalse(dog.hasGameTask(PACKAGE + "/.Main", TARGET));
    }

    @Test
    public void moveRequestsFocusBeforeWaitingForTheFrame() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(0, PACKAGE + "/.Main");
        platform.publishFrame(); // 回迁前的帧
        platform.produceOnFocus = true;
        Watchdog dog = new Watchdog(config(), platform, platform);
        dog.poll();
        dog.poll();

        assertEquals(1, platform.focusCalls);
        assertTrue(platform.events.indexOf("task_display_changed") < platform.events.indexOf("focus_requested"));
        assertTrue(platform.events.indexOf("focus_requested") < platform.events.indexOf("move_back_succeeded"));
        assertEquals(2, platform.details("move_back_succeeded").getLong("first_frame_seq"));
        assertEquals("timestamp", platform.details("move_back_succeeded").getString("frame_boundary"));
    }

    @Test
    public void taskArrivalWithoutFramesTimesOutAndLaterReportsRecovery() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(0, PACKAGE + "/.Main");
        Watchdog.Config config = config();
        config.stallMs = 0;
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        dog.poll();
        platform.now += config.moveTimeoutMs + 1;
        dog.poll();
        dog.poll();

        assertEquals(1, platform.events.stream().filter("move_back_frame_timeout"::equals).count());
        assertFalse(platform.events.contains("move_back_failed"));
        assertFalse(platform.events.contains("move_back_succeeded"));
        platform.publishFrame();
        dog.poll();
        assertTrue(platform.details("move_back_succeeded").getBoolean("late_frame"));
        assertEquals(1, platform.details("move_back_succeeded").getInt("attempt"));
    }

    @Test
    public void moveRejectedByPlatformIsNotAFrameTimeout() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(0, PACKAGE + "/.Main");
        platform.rejectMove = true;
        Watchdog.Config config = config();
        config.maxMoveAttempts = 1;
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        dog.poll();
        assertTrue(platform.details("move_back_failed").getBoolean("final"));
        assertFalse(platform.events.contains("move_back_frame_timeout"));
        assertEquals(0, platform.focusCalls);
    }

    @Test
    public void moveKeepsTheOnlyFramePublishedWhileReadingTheSequence() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(0, PACKAGE + "/.Main");
        platform.publishWhileReadingSequence = true;
        Watchdog.Config config = config();
        config.autoFocus = false;
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        dog.poll();

        assertEquals(1, platform.details("move_back_succeeded").getLong("first_frame_seq"));
    }

    @Test
    public void focusWaitsWhenPowerStateChangesDuringTheMove() throws Exception {
        for (boolean locked : new boolean[] {true, false}) {
            Fixture platform = new Fixture();
            platform.setTask(0, PACKAGE + "/.Main");
            platform.lockOnMove = locked;
            platform.sleepOnMove = !locked;
            platform.produceOnFocus = true;
            Watchdog dog = new Watchdog(config(), platform, platform);
            dog.poll();
            dog.poll();

            assertEquals(0, platform.focusCalls);
            assertFalse(platform.events.contains("focus_requested"));
            assertFalse(platform.events.contains("move_back_succeeded"));

            platform.locked = false;
            platform.awake = true;
            dog.poll();
            assertEquals(1, platform.focusCalls);
            assertTrue(platform.events.contains("move_back_succeeded"));
        }
    }

    @Test
    public void waitsForMainActivityBeforeAllowingInputFocusOrMove() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(TARGET, SDK);
        platform.produceOnFocus = true;
        Watchdog.Config config = config();
        config.mainActivity = null;
        config.stallMs = 1000;
        Watchdog dog = new Watchdog(config, platform, platform);
        assertEquals(Protocol.E_MAIN_ACTIVITY_UNKNOWN,
                assertThrows(CommandException.class, () -> dog.checkInput(TARGET, true)).code);

        dog.poll();
        dog.poll();
        platform.now += config.manualTimeoutMs + 1;
        dog.poll();
        assertEquals(0, platform.focusCalls);
        assertFalse(platform.events.contains("manual_action_required"));
        assertEquals(Protocol.E_MAIN_ACTIVITY_UNKNOWN,
                assertThrows(CommandException.class, () -> dog.checkInput(TARGET, true)).code);

        platform.setTask(0, PACKAGE + "/.Main");
        dog.learnMainActivity("another.app/.Main");
        dog.poll();
        assertEquals(0, platform.moveCalls);

        dog.learnMainActivity(PACKAGE + "/.Main");
        platform.setTask(TARGET, SDK);
        dog.poll();
        assertEquals(Protocol.E_SDK_WINDOW_ACTIVE,
                assertThrows(CommandException.class, () -> dog.checkInput(TARGET, true)).code);
        assertEquals(0, platform.focusCalls);

        platform.setTask(0, PACKAGE + "/.Main");
        dog.poll();
        assertEquals(1, platform.moveCalls);
        assertEquals(1, platform.focusCalls);
        dog.checkInput(TARGET, true);
    }

    @Test
    public void launchDoesNotReplaceConfiguredMainActivity() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(TARGET, SDK);
        Watchdog dog = new Watchdog(config(), platform, platform);
        dog.learnMainActivity(SDK);
        dog.poll();

        assertEquals(MAIN, dog.describe().getString("main_activity"));
        assertEquals(Protocol.E_SDK_WINDOW_ACTIVE,
                assertThrows(CommandException.class, () -> dog.checkInput(TARGET, true)).code);
    }

    @Test
    public void sdkOnTargetBlocksInputAndAutomaticFocusUntilItCloses() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(TARGET, SDK);
        platform.publishFrame();
        platform.produceOnFocus = true;
        Watchdog.Config config = config();
        config.stallMs = 1000;
        config.manualTimeoutMs = 1200;
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        platform.now += config.manualTimeoutMs + 1;
        dog.poll();
        dog.poll();

        assertTrue(platform.events.contains("manual_action_required"));
        assertEquals(0, platform.focusCalls);
        CommandException error = assertThrows(CommandException.class, () -> dog.checkInput(TARGET, true));
        assertEquals(Protocol.E_SDK_WINDOW_ACTIVE, error.code);

        platform.setTask(TARGET, PACKAGE + "/.Main");
        dog.poll();
        dog.checkInput(TARGET, true);
        platform.now += config.stallMs + 1;
        dog.poll();
        assertTrue(platform.events.contains("sdk_window_gone"));
        assertEquals(1, platform.focusCalls);
        dog.poll();
        assertTrue(platform.events.contains("frames_resumed"));
    }

    @Test
    public void focusExperimentIsExplicitAndDoesNotChangeTheDefaultConfig() throws Exception {
        Watchdog.Config regular = Watchdog.Config.fromJson(new JSONObject().put("package", PACKAGE));
        assertFalse(regular.autoFocus);
        assertFalse(regular.stallFocusOnce);
        assertTrue(Watchdog.Config.fromJson(new JSONObject().put("package", PACKAGE)
                .put("stall_focus_once", true)).stallFocusOnce);
    }

    @Test
    public void physicalAndroid12ObservesFocusAndFramesSeparatelyAndNeverRetries() throws Exception {
        for (boolean enabled : new boolean[]{false, true}) {
            for (boolean rendered : new boolean[]{false, true}) {
                Fixture platform = new Fixture();
                platform.setTask(TARGET, PACKAGE + "/.Main");
                platform.publishFrame();
                platform.produceOnFocus = rendered;
                Watchdog.Config config = experimentConfig(enabled);
                Watchdog dog = new Watchdog(config, platform, platform);
                enterStall(dog, platform, config);
                assertEquals(enabled ? 1 : 0, platform.focusCalls);
                if (enabled) {
                    assertEquals(List.of("DOWN@42", "CANCEL@42"), platform.actions);
                    assertEquals("none", platform.details("stall_focus_before").getJSONObject("evidence").getString("target_window_focus"));
                    assertTrue(platform.details("stall_focus_injected").getJSONObject("injection").getBoolean("down_accepted"));
                    dog.poll();
                    platform.now += 5001;
                    dog.poll();
                    JSONObject after = platform.details("stall_focus_after");
                    // 注入被接受、窗口取得焦点，并不代表 Unity 开始出帧。
                    assertTrue(after.getBoolean("focus_acquired"));
                    assertEquals(rendered, after.getBoolean("frame_advanced"));
                    assertTrue(after.getJSONObject("evidence").getJSONObject("game_layers").toString()
                            .contains(rendered ? "1280x720 RGBA_8888" : "0x0 Unknown/None"));
                }
                for (int i = 0; i < 20; i++) {
                    platform.publishFrame();
                    dog.poll();
                    platform.now += config.stallMs + 1;
                    dog.poll();
                }
                assertEquals(enabled ? 1 : 0, platform.focusCalls);
            }
        }
    }

    @Test
    public void experimentRechecksContextAfterDiagnosticsAndAfterWaitingForTheInputLock() throws Exception {
        for (String fault : List.of("frame", "locked", "asleep", "moved", "sdk", "deadline", "stop")) {
            for (boolean inputLock : new boolean[]{false, true}) {
                Fixture platform = new Fixture();
                platform.setTask(TARGET, PACKAGE + "/.Main");
                platform.publishFrame();
                Watchdog.Config config = experimentConfig(true);
                Watchdog dog = new Watchdog(config, platform, platform);
                Runnable injectFault = () -> {
                    switch (fault) {
                        case "frame": platform.publishFrame(); break;
                        case "locked": platform.locked = true; break;
                        case "asleep": platform.awake = false; break;
                        case "moved": platform.setTask(0, PACKAGE + "/.Main"); break;
                        case "sdk": platform.setTask(TARGET, SDK); break;
                        case "deadline": platform.now += 15001; break;
                        case "stop": dog.stop(); break;
                        default: throw new AssertionError(fault);
                    }
                };
                if (inputLock) platform.beforeInjection = injectFault;
                else platform.beforeEvidence = injectFault;
                enterStall(dog, platform, config);
                assertEquals(fault + " inputLock=" + inputLock, 0, platform.focusCalls);
                assertTrue(platform.actions.isEmpty());
                assertTrue(dog.describe().getBoolean("stall_focus_attempted"));
            }
        }
    }

    @Test
    public void unknownOrExistingFocusAndUnavailableDiagnosticsDoNotCauseATouch() throws Exception {
        for (String focus : List.of("game", "other", "unknown", "dump_error")) {
            Fixture platform = new Fixture();
            platform.setTask(TARGET, PACKAGE + "/.Main");
            platform.windowFocus = focus;
            platform.evidenceUnavailable = focus.equals("dump_error");
            Watchdog.Config config = experimentConfig(true);
            Watchdog dog = new Watchdog(config, platform, platform);
            enterStall(dog, platform, config);
            for (int i = 0; i < 20; i++) {
                platform.now += 1000;
                dog.poll();
            }
            assertEquals(0, platform.focusCalls);
            assertEquals(1, platform.evidenceCalls);
            assertTrue(platform.events.contains("stall_focus_skipped"));
        }
    }

    @Test
    public void failedInjectionIsObservedWithoutClaimingFocusOrResending() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(TARGET, PACKAGE + "/.Main");
        platform.focusAccepted = false;
        Watchdog.Config config = experimentConfig(true);
        Watchdog dog = new Watchdog(config, platform, platform);
        enterStall(dog, platform, config);
        platform.now += 5001;
        dog.poll();
        assertFalse(platform.details("stall_focus_injected").getJSONObject("injection").getBoolean("down_accepted"));
        assertFalse(platform.details("stall_focus_after").getBoolean("focus_acquired"));
        assertFalse(platform.details("stall_focus_after").getBoolean("frame_advanced"));
        platform.publishFrame(); // 迟到的正常帧仍可推进，不再发一次恢复触摸。
        dog.poll();
        assertTrue(platform.events.contains("frames_resumed"));
        platform.now += config.stallMs + 1;
        dog.poll();
        assertEquals(1, platform.focusCalls);
    }

    @Test
    public void experimentLeavesOtherAndroidVersionsDisplayZeroAndEmulatorPolicyAlone() throws Exception {
        for (int sdk : new int[]{29, 31, 32, 33, 34, 36}) {
            Fixture platform = new Fixture();
            platform.sdk = sdk;
            platform.setTask(TARGET, PACKAGE + "/.Main");
            Watchdog.Config config = experimentConfig(true);
            Watchdog dog = new Watchdog(config, platform, platform);
            enterStall(dog, platform, config);
            assertEquals(sdk == 31 ? 1 : 0, platform.focusCalls);
        }
        Fixture primary = new Fixture();
        primary.display = 0;
        primary.setTask(0, PACKAGE + "/.Main");
        Watchdog.Config config = experimentConfig(true);
        config.displayId = 0;
        enterStall(new Watchdog(config, primary, primary), primary, config);
        assertEquals(0, primary.focusCalls);
        for (boolean experiment : new boolean[]{false, true}) {
            Fixture emulator = new Fixture();
            emulator.setTask(TARGET, PACKAGE + "/.Main");
            Watchdog.Config emulatorConfig = experimentConfig(experiment);
            emulatorConfig.autoFocus = true;
            enterStall(new Watchdog(emulatorConfig, emulator, emulator), emulator, emulatorConfig);
            assertEquals(1, emulator.focusCalls);
            assertEquals(0, emulator.evidenceCalls);
            assertTrue(emulator.events.contains("focus_requested"));
        }
    }

    @Test
    public void transientStallsAndContinuousBlackBuffersDoNotTriggerTheExperiment() throws Exception {
        Fixture platform = new Fixture();
        platform.setTask(TARGET, PACKAGE + "/.Main");
        Watchdog.Config config = experimentConfig(true);
        Watchdog dog = new Watchdog(config, platform, platform);
        dog.poll();
        for (int i = 0; i < 100; i++) {
            platform.now += config.stallMs / 2;
            platform.publishFrame();
            dog.poll();
        }
        assertEquals(0, platform.focusCalls);
        assertEquals(0, platform.evidenceCalls);
    }

    private static void enterStall(Watchdog dog, Fixture platform, Watchdog.Config config) throws Exception {
        dog.poll();
        dog.poll();
        platform.now += config.stallMs + 1;
        dog.poll();
    }

    private static Watchdog.Config experimentConfig(boolean enabled) {
        Watchdog.Config config = config();
        config.autoFocus = false;
        config.stallFocusOnce = enabled;
        config.stallMs = 1000;
        return config;
    }

    private static Watchdog.Config config() {
        Watchdog.Config config = new Watchdog.Config();
        config.packageName = PACKAGE;
        config.mainActivity = MAIN;
        config.autoFocus = true;
        config.settlePolls = 1;
        return config;
    }

    private static final class Fixture implements Watchdog.Platform, Watchdog.Host {
        final FrameSequencer frames = new FrameSequencer();
        final List<String> events = new ArrayList<>();
        final List<JSONObject> eventFields = new ArrayList<>();
        StackEntry task;
        long now = 2000;
        int focusCalls;
        int moveCalls;
        boolean produceOnFocus;
        boolean rejectMove;
        boolean publishWhileReadingSequence;
        boolean lockOnMove;
        boolean sleepOnMove;
        boolean locked;
        boolean awake = true;
        int sdk = 31;
        int display = TARGET;
        String windowFocus = "none";
        String focusAfter = "game";
        int evidenceCalls;
        Runnable beforeEvidence = () -> {};
        Runnable beforeInjection = () -> {};
        boolean focusAccepted = true;
        boolean evidenceUnavailable;
        final List<String> actions = new ArrayList<>();

        Fixture() {
            frames.setActive(true);
        }

        void setTask(int display, String top) {
            task = new StackEntry(display == TARGET ? 9 : 8, display, true, top);
            task.taskIds.add(17);
            task.taskNames.add(PACKAGE + "/.Main");
        }

        void publishFrame() {
            now += 2;
            frames.publish(nanoTime() - 1, nanoTime(), now);
        }

        JSONObject details(String event) {
            assertTrue("missing event " + event, events.contains(event));
            return eventFields.get(events.indexOf(event));
        }

        @Override
        public long elapsedMs() {
            return now;
        }

        @Override
        public long nanoTime() {
            return now * 1_000_000L;
        }

        @Override
        public int sdkInt() {
            return sdk;
        }

        @Override
        public boolean interactive() {
            return awake;
        }

        @Override
        public boolean keyguardLocked() {
            return locked;
        }

        @Override
        public String processName(int pid) {
            return PACKAGE;
        }

        @Override
        public int findProcess(String packageName) {
            return 123;
        }

        @Override
        public String inspectorMode() {
            return "hidden";
        }

        @Override
        public List<StackEntry> stacks() {
            return task == null ? List.of() : List.of(task);
        }

        @Override
        public void move(int stackId, int displayId) {
            if (rejectMove) {
                throw new IllegalStateException("move rejected");
            }
            moveCalls++;
            setTask(displayId, PACKAGE + "/.Main");
            locked = lockOnMove;
            awake = !sleepOnMove;
        }

        @Override
        public void emit(String type, JSONObject fields) {
            events.add(type);
            eventFields.add(fields);
        }

        @Override
        public int currentDisplayId() {
            return display;
        }

        @Override
        public long latestSeq() {
            if (publishWhileReadingSequence) {
                publishWhileReadingSequence = false;
                publishFrame();
            }
            return frames.latest();
        }

        @Override
        public FrameSequencer.Frame latestFrame(int displayId) {
            return displayId == TARGET ? frames.current() : null;
        }

        @Override
        public void launch(String component, int displayId) {
            throw new AssertionError("the test does not relaunch the game");
        }

        @Override
        public boolean focusDisplay(int displayId) {
            assertEquals(TARGET, displayId);
            assertEquals(TARGET, task.displayId);
            focusCalls++;
            actions.add("DOWN@" + displayId);
            actions.add("CANCEL@" + displayId);
            if (produceOnFocus) {
                publishFrame();
            }
            return true;
        }

        @Override
        public JSONObject focusDisplayDiagnostic(int displayId, BooleanSupplier allowed) throws Exception {
            beforeInjection.run();
            if (!allowed.getAsBoolean()) return FocusInjection.skipped("context_changed_or_stopped_or_deadline").describe();
            return FocusInjection.send(() -> {
                focusCalls++;
                actions.add("DOWN@" + displayId);
                if (focusAccepted) {
                    windowFocus = focusAfter;
                    if (produceOnFocus) publishFrame();
                }
                return focusAccepted;
            }, () -> { actions.add("CANCEL@" + displayId); return true; }).describe();
        }

        @Override
        public JSONObject focusEvidence(int displayId) throws Exception {
            evidenceCalls++;
            beforeEvidence.run();
            if (evidenceUnavailable) throw new CommandException("diagnostic_unavailable", "window dump unavailable");
            String buffer = produceOnFocus && focusCalls > 0 ? "1280x720 RGBA_8888" : "0x0 Unknown/None";
            return new JSONObject().put("target_window_focus", windowFocus)
                    .put("frame", new JSONObject().put("seq", frames.latest()))
                    .put("game_layers", StartupDiagnostics.gameLayers("  + BufferStateLayer (SurfaceView[" + PACKAGE
                            + "/.Main](BLAST)#19953)\n    activeBuffer=[" + buffer + "]\n", PACKAGE));
        }
    }
}
