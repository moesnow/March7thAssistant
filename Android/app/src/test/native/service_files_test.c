// 在临时目录里以真实 Root 创建旧文件，再切到 shell UID 检查访问和记录锁。
#define main launcher_main
#include "../../main/native/launcher.c"
#undef main
#include <assert.h>

static const char *primary = "m7a-device-service.lock";
static const char *cleanup = "m7a-device-service.cleanup.lock";
static const char *audio = "m7a-game-audio";
static const char *state = "m7a-game-audio/org.example.game.state";
static const char *staging = "m7a-game-audio/org.example.game.state.new";

static void wait_exit(pid_t child, int expected) {
    int status;
    assert(child > 0 && waitpid(child, &status, 0) == child);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == expected);
}

static pid_t prepare(void) {
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        prepare_service_files(".");
        _exit(0);
    }
    return child;
}

static struct stat metadata(const char *name) {
    struct stat st;
    assert(lstat(name, &st) == 0);
    return st;
}

static ino_t write_legacy(const char *name, mode_t mode) {
    int fd = open(name, O_WRONLY | O_CREAT | O_EXCL, mode);
    assert(fd >= 0 && write(fd, "12345 allow", 11) == 11 && close(fd) == 0);
    return metadata(name).st_ino;
}

static int hold_lock(const char *name, short type) {
    int fd = open(name, O_RDWR);
    struct flock lock = { .l_type = type, .l_whence = SEEK_SET };
    assert(fd >= 0 && fcntl(fd, F_SETLK, &lock) == 0);
    return fd;
}

static void check_shell(bool accessible, bool busy) {
    pid_t child = fork();
    if (!child) {
        const gid_t inet = INET_GID;
        assert(setgroups(1, &inet) == 0 && setgid(SHELL_UID) == 0 && setuid(SHELL_UID) == 0);
        const char *files[] = {primary, cleanup, state, staging};
        for (size_t i = 0; i < sizeof(files) / sizeof(files[0]); i++) {
            int fd = open(files[i], O_RDWR);
            if (!accessible) {
                assert(fd == -1 && errno == EACCES);
                continue;
            }
            char bytes[11];
            assert(fd >= 0 && read(fd, bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes));
            assert(memcmp(bytes, "12345 allow", sizeof(bytes)) == 0);
            if (i < 2) {
                struct flock lock = { .l_type = F_WRLCK, .l_whence = SEEK_SET };
                int result = fcntl(fd, F_SETLK, &lock);
                if (busy) assert(result == -1 && (errno == EAGAIN || errno == EACCES));
                else assert(result == 0);
            }
            close(fd);
        }
        _exit(0);
    }
    wait_exit(child, 0);
}

int main(void) {
    assert(getuid() == 0);
    char directory[] = "./m7a-service-files-XXXXXX";
    assert(mkdtemp(directory) && chdir(directory) == 0 && chmod(".", 0711) == 0);
    umask(0);
    wait_exit(prepare(), 0);
    assert(access(primary, F_OK) == -1 && errno == ENOENT);

    assert(mkdir(audio, 0700) == 0);
    const char *paths[] = {primary, cleanup, audio, state, staging};
    ino_t inodes[] = {write_legacy(primary, 0600), write_legacy(cleanup, 0644),
                      metadata(audio).st_ino, write_legacy(state, 0400), write_legacy(staging, 0600)};
    check_shell(false, false);
    int owner = hold_lock(primary, F_WRLCK);
    int worker = hold_lock(cleanup, F_RDLCK);
    pid_t first = prepare();
    pid_t second = prepare();
    wait_exit(first, 0);
    wait_exit(second, 0);
    for (size_t i = 0; i < sizeof(paths) / sizeof(paths[0]); i++) {
        struct stat st = metadata(paths[i]);
        assert(st.st_ino == inodes[i] && st.st_uid == SHELL_UID && st.st_gid == SHELL_UID);
        assert((st.st_mode & 07777) == (S_ISDIR(st.st_mode) ? 0700 : 0600));
    }
    check_shell(true, true);
    close(owner);
    close(worker);
    check_shell(true, false);
    assert(chmod(primary, 0640) == 0);
    wait_exit(prepare(), 0);
    assert((metadata(primary).st_mode & 07777) == 0640);

    assert(chown(audio, 0, 0) == 0 && chmod(audio, 01777) == 0);
    assert(chown(staging, 0, 0) == 0 && chmod(staging, 0666) == 0);
    wait_exit(prepare(), 0);
    assert(metadata(audio).st_uid == SHELL_UID && (metadata(audio).st_mode & 07777) == 0700);
    assert(metadata(staging).st_uid == 0 && (metadata(staging).st_mode & 07777) == 0666);
    check_shell(true, false);

    // 异常目标应失败，目录外的文件及不符合记录格式的文件必须保留原状。
    const char *other = "outside";
    ino_t external = write_legacy(other, 0600);
    assert(unlink(state) == 0 && symlink("../outside", state) == 0);
    wait_exit(prepare(), 1);
    assert(unlink(state) == 0 && link(other, state) == 0);
    wait_exit(prepare(), 1);
    assert(unlink(state) == 0 && mkfifo(state, 0600) == 0);
    wait_exit(prepare(), 1);
    assert(unlink(state) == 0 && mkdir(state, 0700) == 0);
    wait_exit(prepare(), 1);
    assert(rmdir(state) == 0);
    write_legacy(state, 0400);
    assert(chown(state, 10001, 10001) == 0);
    wait_exit(prepare(), 1);
    assert(metadata(state).st_uid == 10001 && unlink(state) == 0);
    const char *unrelated = "m7a-game-audio/not-a-package.state";
    assert(symlink("../outside", unrelated) == 0);
    wait_exit(prepare(), 0);
    assert(metadata(other).st_ino == external && metadata(other).st_uid == 0);
    assert((metadata(other).st_mode & 07777) == 0600);
    assert(unlink(unrelated) == 0 && unlink(staging) == 0 && rmdir(audio) == 0);
    assert(symlink(".", audio) == 0);
    wait_exit(prepare(), 1);
    assert(unlink(audio) == 0 && unlink(primary) == 0 && unlink(cleanup) == 0 && unlink(other) == 0);
    assert(chdir("..") == 0 && rmdir(directory) == 0);
    return 0;
}
