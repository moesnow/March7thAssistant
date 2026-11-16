package org.march7th.deviceservice.core;

import android.media.AudioManager;
import android.media.AudioPlaybackConfiguration;
import android.os.DeadObjectException;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Process;
import android.util.Log;

import org.march7th.deviceservice.protocol.Protocol;

import java.io.IOException;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** AppOps 未生效时，用系统音频服务控制指定 UID 的播放器。 */
final class PlayerVolumeFallback implements GameAudio.Players {
    private final Set<Integer> mutedUids = new HashSet<>();
    private AudioManager audio;
    private Method clientUid;
    private Method isActive;
    private Method getPlayer;
    private Method setVolume;
    private HandlerThread thread;
    private final AudioManager.AudioPlaybackCallback callback = new AudioManager.AudioPlaybackCallback() {
        @Override
        public void onPlaybackConfigChanged(List<AudioPlaybackConfiguration> configurations) {
            synchronized (PlayerVolumeFallback.this) {
                try {
                    apply(configurations, mutedUids, 0f);
                } catch (IOException error) {
                    // 善后进程的 stdout 是命令回执通道。
                    Log.w(Protocol.LOG_TAG, "cannot mute newly active game players", error);
                }
            }
        }
    };

    @Override
    public void prepare() throws IOException {
        if (audio != null) {
            return;
        }
        try {
            if (!SystemApis.canControlPlayers(Process.myUid())) {
                throw new IOException("MODIFY_AUDIO_ROUTING is unavailable");
            }
            clientUid = AudioPlaybackConfiguration.class.getMethod("getClientUid");
            isActive = AudioPlaybackConfiguration.class.getMethod("isActive");
            getPlayer = AudioPlaybackConfiguration.class.getDeclaredMethod("getIPlayer");
            getPlayer.setAccessible(true);
            setVolume = Class.forName("android.media.IPlayer").getMethod("setVolume", float.class);
            // 只有播放配置与回调接口，不需要 Context。
            audio = AudioManager.class.getConstructor().newInstance();
        } catch (ReflectiveOperationException | RuntimeException error) {
            throw new IOException("player volume API unavailable: " + Logger.describe(error), error);
        }
    }

    @Override
    public synchronized void mute(int uid) throws IOException {
        if (thread == null) {
            HandlerThread handlerThread = new HandlerThread("m7a-game-audio");
            handlerThread.start();
            try {
                audio.registerAudioPlaybackCallback(callback, new Handler(handlerThread.getLooper()));
                thread = handlerThread;
            } catch (RuntimeException error) {
                handlerThread.quitSafely();
                throw new IOException("cannot listen for game players: " + Logger.describe(error), error);
            }
        }
        mutedUids.add(uid);
        apply(currentPlayers(), Collections.singleton(uid), 0f);
    }

    @Override
    public synchronized void restore(int uid) throws IOException {
        // 已排队的回调在锁释放后也不会再向这个 UID 写入 0。
        mutedUids.remove(uid);
        if (mutedUids.isEmpty() && thread != null) {
            try {
                audio.unregisterAudioPlaybackCallback(callback);
            } catch (RuntimeException error) {
                Log.w(Protocol.LOG_TAG, "cannot unregister the game player callback", error);
            } finally {
                thread.quitSafely();
                thread = null;
            }
        }
        prepare();
        apply(currentPlayers(), Collections.singleton(uid), 1f);
    }

    private List<AudioPlaybackConfiguration> currentPlayers() throws IOException {
        try {
            return audio.getActivePlaybackConfigurations();
        } catch (RuntimeException error) {
            throw new IOException("cannot read active game players: " + Logger.describe(error), error);
        }
    }

    private void apply(List<AudioPlaybackConfiguration> configurations, Set<Integer> uids, float volume)
            throws IOException {
        IOException failure = null;
        for (AudioPlaybackConfiguration configuration : configurations) {
            try {
                int uid = (Integer) clientUid.invoke(configuration);
                if (uid < 0) {
                    throw new IOException("playback configurations do not identify the player's UID");
                }
                if (!uids.contains(uid)) {
                    continue;
                }
                Object player = getPlayer.invoke(configuration);
                if (player == null) {
                    // 播放器可能刚释放；仍在播放却拿不到控制接口时保留恢复记录。
                    if (Boolean.TRUE.equals(isActive.invoke(configuration))) {
                        failure = new IOException("active game player is not accessible");
                    }
                    continue;
                }
                setVolume.invoke(player, volume);
            } catch (ReflectiveOperationException | RuntimeException error) {
                if (!(error instanceof InvocationTargetException && error.getCause() instanceof DeadObjectException)) {
                    failure = new IOException("cannot change game player volume: " + Logger.describe(error), error);
                }
            }
        }
        if (failure != null) {
            throw failure;
        }
    }
}
