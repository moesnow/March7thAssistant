# app_process 按类名启动 AppServer，设备端也在 APK 之外执行系统调用。
-keep class org.march7th.deviceservice.** { *; }

# Shizuku 按组件名反射构造 UserService，双方经同一个 AIDL 接口通信。
-keep class org.march7th.assistant.GameUserService {
    public <init>(android.content.Context);
}
-keep interface org.march7th.assistant.IDeviceBootstrap { *; }
-keep class org.march7th.assistant.IDeviceBootstrap$* { *; }

# Python 通过 Chaquopy 按成员名调用。
-keepclassmembers class org.march7th.assistant.TaskController$TaskRun {
    public boolean isCancelled();
    public void log(long, java.lang.String, java.lang.String, java.lang.String, boolean);
    public void reportSummary(java.lang.String);
    public void reportStep(java.lang.String, java.lang.String, java.lang.String);
    public void reportProgress(java.lang.String);
    public int openDevice();
    public void displayReady(int);
    public void gameEvent(java.lang.String, int);
    public void gameReady();
    public void panelChanged(boolean);
    public void cleaning();
}
