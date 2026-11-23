// 使用真实 fork、管道与 waitpid。替换身份系统调用和最终 exec，无需 Root 或游戏。
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static pid_t launcher_pid;
static uid_t initial_uid, current_uid;
static int stage, deny_groups, direct_root, recovery, prepared;
static char directory[] = "./m7a-launcher-XXXXXX";

static uid_t checked_uid(void) {
    assert((getpid() == launcher_pid) == direct_root);
    return current_uid;
}

static int open_fixture(const char *name, int flags) {
    assert(checked_uid() == 0 && stage == 0 && strcmp(name, "/data/local/tmp") == 0);
    prepared = 1;
    return open(directory, flags);
}

static int checked_groups(size_t count, const gid_t *groups) {
    assert(checked_uid() == 0 && prepared && stage++ == 0 && count == 1 && groups[0] == 3003);
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
    va_list args;
    va_start(args, arg0);
    assert(strcmp(va_arg(args, const char *), "/system/bin") == 0);
    assert(strcmp(va_arg(args, const char *), direct_root ? "--nice-name=m7a-apk-root" : "--nice-name=m7a-apk-shizuku") == 0);
    assert(strcmp(va_arg(args, const char *), "org.march7th.deviceservice.AppServer") == 0);
    assert(strcmp(va_arg(args, const char *), "/test/base.apk") == 0);
    if (recovery) assert(strcmp(va_arg(args, const char *), "--recover-audio") == 0);
    assert(va_arg(args, const char *) == NULL);
    va_end(args);
    _exit(0);
}

#define getuid checked_uid
#define open open_fixture
#define geteuid checked_uid
#define setgroups checked_groups
#define setresgid checked_gid
#define setresuid checked_setuid
#define execl checked_exec
#define main launcher_main
#include "../../main/native/launcher.c"
#undef main

static void run_as(uid_t uid, int deny, int direct, int recover, int expected) {
    pid_t pid = fork();
    assert(pid >= 0);
    if (pid == 0) {
        launcher_pid = getpid();
        initial_uid = current_uid = uid;
        deny_groups = deny;
        direct_root = direct;
        recovery = recover;
        char *args[5] = { "launcher" };
        int argc = 1;
        if (direct) args[argc++] = "--root";
        args[argc++] = "/test/base.apk";
        if (recover) args[argc++] = "--recover-audio";
        _exit(launcher_main(argc, args));
    }
    int status;
    assert(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == expected);
}

int main(void) {
    assert(mkdtemp(directory));
    for (int recover = 0; recover <= 1; recover++) {
        run_as(2000, 0, 0, recover, 0);
        run_as(0, 0, 0, recover, 0);
        run_as(0, 0, 1, recover, 0);
    }
    run_as(0, 1, 0, 0, 1);
    run_as(10001, 0, 0, 0, 2);
    assert(rmdir(directory) == 0);
    return 0;
}
