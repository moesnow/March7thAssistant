package org.march7th.deviceservice.core;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

public class GameAudioTest {
    private static final String PACKAGE = "example.game";
    private static final int UID = 10123;

    @Rule
    public final TemporaryFolder folder = new TemporaryFolder();

    @Test
    public void newProcessRestoresTheRecordedAppOps() throws Exception {
        FakeAudio audio = new FakeAudio();
        audio.mode = "foreground";
        assertEquals("foreground", audio.service().setMuted(PACKAGE, true));
        assertEquals("ignore", audio.mode);
        assertEquals(0, audio.playerWrites.size());

        audio.service().restorePending();
        assertEquals("foreground", audio.mode);
        assertFalse(Files.exists(record()));
    }

    @Test
    public void rollsBackThePackageModeBeforeFallingBackToThePlayer() throws Exception {
        FakeAudio audio = new FakeAudio();
        audio.effectiveOverride = "allow";
        GameAudio service = audio.service();
        assertEquals("allow", service.setMuted(PACKAGE, true));
        assertEquals(List.of("ignore", "allow"), audio.appOpsWrites);
        assertEquals(List.of(0f), audio.playerWrites);
        assertTrue(Files.exists(record()));

        // 新实例没有任何内存状态，按记录恢复同一 UID 的播放器。
        audio.service().restorePending();
        assertEquals(List.of(0f, 1f), audio.playerWrites);
        assertFalse(Files.exists(record()));
    }

    @Test
    public void neverChangesAnExistingMute() throws Exception {
        FakeAudio audio = new FakeAudio();
        audio.mode = "ignore";
        GameAudio service = audio.service();
        assertEquals("ignore", service.setMuted(PACKAGE, true));
        assertEquals("ignore", service.setMuted(PACKAGE, false));
        assertTrue(audio.appOpsWrites.isEmpty());
        assertTrue(audio.playerWrites.isEmpty());
        assertFalse(Files.exists(record()));
    }

    @Test
    public void keepsUnconfirmedRecoveryForTheNextRestart() throws Exception {
        FakeAudio audio = new FakeAudio();
        audio.service().setMuted(PACKAGE, true);
        audio.rejectWrites = true;
        assertThrows(IOException.class, audio.service()::restorePending);
        assertTrue(Files.exists(record()));
        assertEquals("ignore", audio.mode);

        audio.rejectWrites = false;
        audio.service().restorePending();
        assertEquals("allow", audio.mode);
        assertFalse(Files.exists(record()));
    }

    @Test
    public void skipsAStaleRecordIfThePackageUidChanged() throws Exception {
        FakeAudio audio = new FakeAudio();
        audio.service().setMuted(PACKAGE, true);
        audio.uid++;
        audio.appOpsWrites.clear();
        audio.service().restorePending();
        assertTrue(audio.appOpsWrites.isEmpty());
        assertFalse(Files.exists(record()));
    }

    private Path record() {
        return folder.getRoot().toPath().resolve(PACKAGE + ".state");
    }

    private final class FakeAudio implements GameAudio.AppOps, GameAudio.Players {
        final List<String> appOpsWrites = new ArrayList<>();
        final List<Float> playerWrites = new ArrayList<>();
        String mode = "allow";
        String effectiveOverride;
        int uid = UID;
        boolean rejectWrites;

        GameAudio service() {
            return new GameAudio(folder.getRoot().toPath(), this, this);
        }

        @Override
        public int packageUid(String packageName, int userId) {
            assertEquals(PACKAGE, packageName);
            return uid;
        }

        @Override
        public String mode(String packageName, int uid) {
            return mode;
        }

        @Override
        public String effectiveMode(String packageName, int uid) {
            return effectiveOverride == null ? mode : effectiveOverride;
        }

        @Override
        public void setMode(String packageName, int uid, String newMode) {
            assertTrue(Files.exists(record()));
            appOpsWrites.add(newMode);
            if (!rejectWrites) {
                mode = newMode;
            }
        }

        @Override
        public void prepare() {
        }

        @Override
        public void mute(int uid) {
            assertEquals(UID, uid);
            assertTrue(Files.exists(record()));
            playerWrites.add(0f);
        }

        @Override
        public void restore(int uid) {
            assertEquals(UID, uid);
            assertTrue(Files.exists(record()));
            playerWrites.add(1f);
        }
    }
}
