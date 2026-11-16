package org.march7th.deviceservice.core;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.HashMap;
import java.util.Map;

/** 善后进程持有音频改动。两级静音都在写入恢复记录之后执行。 */
public final class GameAudio {
    private static final Path RECORDS = Paths.get("/data/local/tmp/m7a-game-audio");
    private static final String SUFFIX = ".state";
    private static final String PLAYERS = "players";
    private static final String UNKNOWN = "unknown";

    interface AppOps {
        int packageUid(String packageName, int userId) throws IOException;
        String mode(String packageName, int uid) throws IOException, InterruptedException;
        String effectiveMode(String packageName, int uid) throws IOException, InterruptedException;
        void setMode(String packageName, int uid, String mode) throws IOException, InterruptedException;
    }

    interface Players {
        void prepare() throws IOException;
        void mute(int uid) throws IOException;
        void restore(int uid) throws IOException;
    }

    private final Path directory;
    private final AppOps appOps;
    private final Players players;
    private final Map<String, String> muted = new HashMap<>();

    public GameAudio() {
        this(RECORDS, new AndroidAppOps(), new PlayerVolumeFallback());
    }

    GameAudio(Path directory, AppOps appOps, Players players) {
        this.directory = directory;
        this.appOps = appOps;
        this.players = players;
    }

    public String setMuted(String packageName, boolean on) throws IOException, InterruptedException {
        Path record = recordPath(packageName);
        if (on && muted.containsKey(packageName)) {
            return muted.get(packageName);
        }
        String restored = restore(packageName, record);
        if (!on && restored != null) {
            return restored;
        }
        int uid = appOps.packageUid(packageName, -1);
        if (uid < 10_000) {
            throw new IOException("cannot resolve game UID: " + packageName);
        }
        String original = UNKNOWN;
        IOException appOpsFailure = null;
        try {
            original = appOps.mode(packageName, uid);
            if (on && isMuted(appOps.effectiveMode(packageName, uid))) {
                return "ignore";
            }
        } catch (IOException error) {
            appOpsFailure = error;
        }
        if (!on) {
            if (appOpsFailure != null) {
                throw appOpsFailure;
            }
            if ("default".equals(original)) {
                // 修复早期版本显式写入的 default。
                restoreAppOps(packageName, uid, "allow");
                return "allow";
            }
            return original;
        }
        if ("default".equals(original)) {
            original = "allow"; // 早期版本遗留的模式
        }
        if (appOpsFailure == null) {
            register(record, uid, original);
            try {
                appOps.setMode(packageName, uid, "ignore");
                String actual = appOps.effectiveMode(packageName, uid);
                if (!"ignore".equals(actual)) {
                    throw new IOException("PLAY_AUDIO stayed at " + actual);
                }
                muted.put(packageName, original);
                return original;
            } catch (IOException error) {
                // 包级写入可能已生效而有效值被 UID 级覆盖。先恢复包级再降级。
                restore(packageName, record);
                appOpsFailure = error;
            }
        }
        try {
            players.prepare();
            register(record, uid, PLAYERS);
            players.mute(uid);
        } catch (IOException error) {
            restore(packageName, record);
            throw new IOException(appOpsFailure.getMessage() + " / " + error.getMessage(), error);
        }
        muted.put(packageName, original);
        return original;
    }

    private static boolean isMuted(String mode) {
        return "ignore".equals(mode) || "deny".equals(mode);
    }

    /** 持有实例锁并交接完旧清理进程后，或在旧进程收到 EOF 时调用。 */
    public void restorePending() throws IOException, InterruptedException {
        IOException failure = null;
        try (DirectoryStream<Path> records = Files.newDirectoryStream(directory, "*" + SUFFIX)) {
            for (Path record : records) {
                String name = record.getFileName().toString();
                try {
                    restore(name.substring(0, name.length() - SUFFIX.length()), record);
                } catch (IOException error) {
                    failure = error;
                }
            }
        } catch (NoSuchFileException absent) {
            return;
        }
        if (failure != null) {
            throw failure;
        }
    }

    private Path recordPath(String packageName) throws IOException {
        if (!packageName.matches("[A-Za-z0-9_.]+")) {
            throw new IOException("invalid game package");
        }
        return directory.resolve(packageName + SUFFIX);
    }

    private static void register(Path record, int uid, String original) throws IOException {
        Files.createDirectories(record.getParent());
        Path staging = record.resolveSibling(record.getFileName() + ".new");
        ByteBuffer data = StandardCharsets.UTF_8.encode(uid + " " + original);
        try (FileChannel output = FileChannel.open(staging, StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE)) {
            while (data.hasRemaining()) {
                output.write(data);
            }
            output.force(true);
        }
        Files.move(staging, record, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }

    private String restore(String packageName, Path record) throws IOException, InterruptedException {
        final String text;
        try {
            text = new String(Files.readAllBytes(record), StandardCharsets.UTF_8);
        } catch (NoSuchFileException absent) {
            return null;
        }
        String[] fields = text.split(" ", -1);
        if (fields.length != 2 || !fields[0].matches("[0-9]{5,10}") || !fields[1].matches("[a-z_]+")) {
            throw new IOException("invalid audio recovery record for " + packageName);
        }
        final int uid;
        try {
            uid = Integer.parseInt(fields[0]);
        } catch (NumberFormatException error) {
            throw new IOException("invalid audio recovery UID for " + packageName, error);
        }
        String mode = fields[1];
        if (appOps.packageUid(packageName, AudioAppOps.userId(uid)) == uid) {
            if (PLAYERS.equals(mode)) {
                players.restore(uid);
            } else {
                restoreAppOps(packageName, uid, mode);
            }
        }
        Files.delete(record);
        String original = muted.remove(packageName);
        return PLAYERS.equals(mode) ? (original == null ? UNKNOWN : original) : mode;
    }

    private void restoreAppOps(String packageName, int uid, String original) throws IOException, InterruptedException {
        if (!original.equals(appOps.mode(packageName, uid))) {
            appOps.setMode(packageName, uid, original);
            if (!original.equals(appOps.mode(packageName, uid))) {
                throw new IOException("could not restore PLAY_AUDIO of " + packageName + " to " + original);
            }
        }
    }

    private static final class AndroidAppOps implements AppOps {
        @Override
        public int packageUid(String packageName, int userId) throws IOException {
            try {
                return userId == -1 ? SystemApis.packageUidForCurrentUser(packageName)
                        : SystemApis.packageUid(packageName, userId);
            } catch (ReflectiveOperationException | RuntimeException error) {
                throw new IOException("cannot resolve game UID: " + Logger.describe(error), error);
            }
        }

        @Override
        public String mode(String packageName, int uid) throws IOException, InterruptedException {
            return AudioAppOps.mode(packageName, uid);
        }

        @Override
        public String effectiveMode(String packageName, int uid) throws IOException, InterruptedException {
            return AudioAppOps.effectiveMode(packageName, uid);
        }

        @Override
        public void setMode(String packageName, int uid, String mode) throws IOException, InterruptedException {
            AudioAppOps.setModeAndWait(packageName, uid, mode);
        }
    }
}
