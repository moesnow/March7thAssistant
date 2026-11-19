package top.m7a;

import java.io.BufferedReader;
import java.io.InputStreamReader;

/** 独立 JVM 子进程，让测试使用真实的有限容量管道、退出码和 EOF。 */
public final class DeviceProcessFixture {
    public static void main(String[] args) throws Exception {
        Thread guard = new Thread(() -> {
            try {
                Thread.sleep(10000);
                Runtime.getRuntime().halt(97);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        });
        guard.setDaemon(true);
        guard.start();
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        String mode = args[0];
        if (mode.equals("early-exit")) System.exit(126);
        if (mode.equals("no-ready")) {
            if (in.readLine() != null) System.exit(9);
            return;
        }
        if (mode.equals("audio")) return;
        if (mode.equals("stderr")) {
            System.err.println("M7A_APP_STDIN_READY");
            System.err.println("M7A_APP_PORT 1");
            System.err.println("x".repeat(1024 * 1024));
        }
        System.out.println("M7A_APP_STDIN_READY");
        String token = in.readLine();
        if (token == null) return;
        switch (mode) {
            case "busy":
                System.out.println("M7A_APP_BUSY");
                return;
            case "invalid-port":
                System.err.println("rejected " + token);
                System.out.println("M7A_APP_PORT 65536");
                return;
            case "no-port": break;
            default: System.out.println("M7A_APP_PORT 4321");
        }
        if (in.readLine() != null) System.exit(8);
    }
}
