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

public class WatchdogTest {
    private static final String PACKAGE = "example.game";
    private static final String MAIN = PACKAGE + ".Main";
    private static final String SDK = PACKAGE + "/.Login";
    private static final int TARGET = 42;

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
            return List.of(task);
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
            return TARGET;
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
            if (produceOnFocus) {
                publishFrame();
            }
            return true;
        }
    }
}
