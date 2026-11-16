package top.m7a;

interface IDeviceBootstrap {
    int start(String token, IBinder owner) = 0;
    int recoverAudio() = 1;
    void destroy() = 16777114;
}
