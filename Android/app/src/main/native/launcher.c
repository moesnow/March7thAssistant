#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

enum { SHELL_UID = 2000, INET_GID = 3003 };

static void fail(const char *stage) {
    perror(stage);
    _exit(1);
}

// 旧 Root UserService 可能留下 shell 无法读写的锁和音频恢复记录。
// 只修改已验证描述符的元数据，正式加锁和恢复仍由 AppServer 完成。
static void file_error(const char *directory, const char *name, const char *stage, int error) {
    fprintf(stderr, "prepare service files: %s: %s (errno=%d): %s/%s\n",
            stage, strerror(error), error, directory, name);
    puts("M7A_APP_FILES_FAILED");
    fflush(stdout);
    _exit(1);
}

// -1 仅表示文件尚未创建，或旧善后进程刚刚移走了记录。
static int open_for_shell(int parent, const char *directory, const char *name, bool is_directory) {
    int path = openat(parent, name, O_PATH | O_NOFOLLOW | O_CLOEXEC);
    if (path == -1) {
        if (errno == ENOENT) return -1;
        file_error(directory, name, "open", errno);
    }
    struct stat st;
    if (fstat(path, &st) == -1) file_error(directory, name, "stat", errno);
    if (st.st_nlink == 0) {
        close(path);
        return -1;
    }
    if (is_directory ? !S_ISDIR(st.st_mode) : (!S_ISREG(st.st_mode) || st.st_nlink != 1))
        file_error(directory, name, "unexpected type or link count", EINVAL);
    if (st.st_uid != 0 && st.st_uid != SHELL_UID)
        file_error(directory, name, "unexpected owner", EPERM);

    mode_t required = is_directory ? 7 : 6;
    mode_t access = st.st_mode;
    if (st.st_uid == SHELL_UID) access >>= 6;
    else if (st.st_gid == SHELL_UID || st.st_gid == INET_GID) access >>= 3;
    // Root 的粘滞目录即使可写，也不允许 shell 删除其中旧 Root 的记录。
    bool migrate = (access & required) != required ||
            (is_directory && st.st_uid == 0 && (st.st_mode & S_ISVTX));
    if (!migrate && !is_directory) return path;

    // O_PATH 不会打开特殊设备。校验之后从描述符重开同一 inode，路径被替换也不会跟过去。
    char pinned[64];
    snprintf(pinned, sizeof(pinned), "/proc/self/fd/%d", path);
    int fd = open(pinned, O_RDONLY | O_CLOEXEC | (is_directory ? O_DIRECTORY : 0));
    if (fd == -1) file_error(directory, name, "reopen", errno);
    close(path);
    if (migrate) {
        mode_t mode = required << 6;
        if ((st.st_mode & 07777) != mode && fchmod(fd, mode) == -1)
            file_error(directory, name, "chmod", errno);
        if (st.st_uid == 0 && fchown(fd, SHELL_UID, SHELL_UID) == -1)
            file_error(directory, name, "chown", errno);
    }
    return fd;
}

static bool audio_record(const char *name) {
    // 与 GameAudio.recordPath() 和 register() 使用的包名、后缀一致。
    size_t length = strspn(name, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.");
    if (name[length] != '\0') return false;
    const char *suffixes[] = { ".state", ".state.new" };
    for (size_t i = 0; i < sizeof(suffixes) / sizeof(suffixes[0]); i++) {
        size_t suffix = strlen(suffixes[i]);
        if (length > suffix && strcmp(name + length - suffix, suffixes[i]) == 0) return true;
    }
    return false;
}

static void prepare_service_files(const char *directory) {
    int parent = open(directory, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent == -1) file_error(directory, ".", "open", errno);
    const char *locks[] = { "m7a-device-service.lock", "m7a-device-service.cleanup.lock" };
    for (size_t i = 0; i < sizeof(locks) / sizeof(locks[0]); i++) {
        int fd = open_for_shell(parent, directory, locks[i], false);
        if (fd != -1) close(fd);
    }
    const char *audio = "m7a-game-audio";
    int records = open_for_shell(parent, directory, audio, true);
    close(parent);
    if (records == -1) return;
    DIR *entries = fdopendir(records);
    if (!entries) file_error(directory, audio, "fdopendir", errno);
    struct timespec start, now;
    if (clock_gettime(CLOCK_MONOTONIC, &start) == -1) fail("clock_gettime");
    while (true) {
        errno = 0;
        struct dirent *entry = readdir(entries);
        if (!entry) {
            if (errno) file_error(directory, audio, "readdir", errno);
            break;
        }
        if (clock_gettime(CLOCK_MONOTONIC, &now) == -1) fail("clock_gettime");
        if (now.tv_sec - start.tv_sec >= 5) file_error(directory, audio, "scan", ETIMEDOUT);
        if (audio_record(entry->d_name)) {
            int fd = open_for_shell(records, audio, entry->d_name, false);
            if (fd != -1) close(fd);
        }
    }
    closedir(entries);
}

static int exec_service(const char *apk, const char *option, const char *nice_name) {
    if (getuid() == 0) {
        prepare_service_files("/data/local/tmp");
        const gid_t inet = INET_GID;
        if (setgroups(1, &inet) || setresgid(SHELL_UID, SHELL_UID, SHELL_UID) ||
            setresuid(SHELL_UID, SHELL_UID, SHELL_UID)) fail("drop to shell");
    }
    if (getuid() != SHELL_UID || geteuid() != SHELL_UID) return 2;
    if (setenv("CLASSPATH", apk, 1) == -1) fail("classpath");
    execl("/system/bin/app_process", "app_process", "/system/bin", nice_name,
          "org.march7th.deviceservice.AppServer", apk, option, (char *)NULL);
    fail("app_process");
    return 1;
}

// 子进程 stdin 的唯一写端属于 launcher。App 的管道 EOF、Shizuku 退出或
// launcher 被 Shizuku 终止，都会让 AppServer 收到 EOF 并自行善后。
static void *relay_owner(void *arg) {
    int sink = *(int *)arg;
    char buf[256];
    struct pollfd input = { .fd = STDIN_FILENO, .events = POLLIN };
    // 创建进程后调用方可能还没来得及取得 stdin 就消失了。
    if (TEMP_FAILURE_RETRY(poll(&input, 1, 20000)) > 0) {
        ssize_t n;
        while ((n = TEMP_FAILURE_RETRY(read(STDIN_FILENO, buf, sizeof buf))) > 0) {
            for (ssize_t offset = 0; offset < n;) {
                ssize_t sent = TEMP_FAILURE_RETRY(write(sink, buf + offset, n - offset));
                if (sent <= 0) goto closed;
                offset += sent;
            }
        }
    }
closed:
    close(sink);
    return NULL;
}

int main(int argc, char **argv) {
    bool direct_root = argc > 1 && strcmp(argv[1], "--root") == 0;
    if (direct_root) {
        argc--;
        argv++;
    }
    if (argc != 2 && !(argc == 3 && strcmp(argv[2], "--recover-audio") == 0)) return 2;
    // 直接 Root 已经独占 su 的 stdin，原地 exec 保留其 EOF 和退出码。
    if (direct_root) return exec_service(argv[1], argv[2], "--nice-name=m7a-apk-root");
    int owner[2];
    if (pipe2(owner, O_CLOEXEC) == -1) fail("owner pipe");
    pid_t child = fork();
    if (child == -1) fail("fork");
    if (child == 0) {
        close(owner[1]);
        if (dup2(owner[0], STDIN_FILENO) == -1) fail("owner stdin");
        close(owner[0]);
        return exec_service(argv[1], argv[2], "--nice-name=m7a-apk-shizuku");
    }
    close(owner[0]);
    signal(SIGPIPE, SIG_IGN);
    pthread_t relay;
    int error = pthread_create(&relay, NULL, relay_owner, &owner[1]);
    if (error) {
        close(owner[1]);
        fprintf(stderr, "owner relay: %s\n", strerror(error));
    }
    int status;
    if (TEMP_FAILURE_RETRY(waitpid(child, &status, 0)) == -1) fail("waitpid");
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
