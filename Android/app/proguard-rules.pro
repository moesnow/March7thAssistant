# app_process 按类名启动 AppServer，设备端也在 APK 之外执行系统调用。
-keep class org.march7th.deviceservice.** { *; }

# Shizuku API 13 进程入口与远端管道使用 SDK 自带的 Binder 协议。
-keep interface moe.shizuku.server.IShizukuService { *; }
-keep class moe.shizuku.server.IShizukuService$* { *; }
-keep interface moe.shizuku.server.IRemoteProcess { *; }
-keep class moe.shizuku.server.IRemoteProcess$* { *; }

# Python 通过 Chaquopy 按成员名调用。
-keepclassmembers class top.m7a.TaskController$TaskRun {
    public boolean isCancelled();
    public void ocrStarting();
    public void ocrReady(long);
    public void log(long, java.lang.String, java.lang.String, java.lang.String, boolean);
    public void reportSummary(java.lang.String);
    public void reportStep(java.lang.String, java.lang.String, java.lang.String);
    public void reportProgress(java.lang.String);
    public int openDevice();
    public void audioRecoveryPending(boolean);
    public void previewReady(int);
    public void displayReady(int);
    public void gameEvent(java.lang.String, int);
    public void gameReady(long);
    public void panelChanged(boolean);
    public void cleaning();
}
