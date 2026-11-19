// 使用真实 fork、管道与 waitpid。替换身份系统调用和最终 exec，无需 Root 或游戏。
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <grp.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static pid_t launcher_pid;
static uid_t initial_uid, current_uid;
static int stage, deny_groups;

static uid_t checked_uid(void) {
    assert(getpid() != launcher_pid);
    return current_uid;
}

static int checked_groups(size_t count, const gid_t *groups) {
    assert(checked_uid() == 0 && stage++ == 0 && count == 1 && groups[0] == 3003);
    if (deny_groups) { errno = EPERM; return -1; }
    return 0;
}

static int checked_gid(gid_t real, gid_t effective, gid_t saved) {
    assert(checked_uid() == 0 && stage++ == 1 && real == 2000 && effective == real && saved == real);
    return 0;
}

static int checked_setuid(uid_t real, uid_t effective, uid_t saved) {
    assert(checked_uid() == 0 && stage++ == 2 && real == 2000 && effective == real && saved == real);
    current_uid = real;
    return 0;
}

static int checked_exec(const char *path, const char *arg0, ...) {
    assert(checked_uid() == 2000 && stage == (initial_uid == 0 ? 3 : 0));
    assert(strcmp(path, "/system/bin/app_process") == 0 && strcmp(arg0, "app_process") == 0);
    assert(strcmp(getenv("CLASSPATH"), "/test/base.apk") == 0);
    _exit(0);
}

#define getuid checked_uid
#define geteuid checked_uid
#define setgroups checked_groups
#define setresgid checked_gid
#define setresuid checked_setuid
#define execl checked_exec
#define main launcher_main
#include "../../main/native/launcher.c"
#undef main

static void run_as(uid_t uid, int deny, int expected) {
    pid_t pid = fork();
    assert(pid >= 0);
    if (pid == 0) {
        launcher_pid = getpid();
        initial_uid = current_uid = uid;
        deny_groups = deny;
        char *args[] = { "launcher", "/test/base.apk", NULL };
        _exit(launcher_main(2, args));
    }
    int status;
    assert(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == expected);
}

int main(void) {
    run_as(2000, 0, 0);
    run_as(0, 0, 0);
    run_as(0, 1, 1);
    run_as(10001, 0, 2);
    return 0;
}
