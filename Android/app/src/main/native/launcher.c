#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

enum { SHELL_UID = 2000, INET_GID = 3003 };

static void fail(const char *stage) {
    perror(stage);
    _exit(1);
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
    if (argc != 2 && !(argc == 3 && strcmp(argv[2], "--recover-audio") == 0)) return 2;
    int owner[2];
    if (pipe2(owner, O_CLOEXEC) == -1) fail("owner pipe");
    pid_t child = fork();
    if (child == -1) fail("fork");
    if (child == 0) {
        close(owner[1]);
        if (dup2(owner[0], STDIN_FILENO) == -1) fail("owner stdin");
        close(owner[0]);
        if (getuid() == 0) {
            const gid_t inet = INET_GID;
            if (setgroups(1, &inet) || setresgid(SHELL_UID, SHELL_UID, SHELL_UID) ||
                setresuid(SHELL_UID, SHELL_UID, SHELL_UID)) fail("drop to shell");
        }
        if (getuid() != SHELL_UID || geteuid() != SHELL_UID) return 2;
        if (setenv("CLASSPATH", argv[1], 1) == -1) fail("classpath");
        execl("/system/bin/app_process", "app_process", "/system/bin", "--nice-name=m7a-apk-shizuku",
              "org.march7th.deviceservice.AppServer", argv[1], argv[2], (char *)NULL);
        fail("app_process");
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
