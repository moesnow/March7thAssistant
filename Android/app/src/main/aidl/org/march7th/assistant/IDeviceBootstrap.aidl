package org.march7th.assistant;

interface IDeviceBootstrap {
    int start(String token, IBinder owner) = 0;
    void destroy() = 16777114;
}
