package org.march7th.deviceservice.core;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/** 执行系统命令。只用于不频繁的操作（启动应用、AppOps、取任务列表的后备路径），输入注入不走这里。 */
final class Shell {
    static final class Result {
        final int exitCode;
        final String stdout;
        final String stderr;

        Result(int exitCode, String stdout, String stderr) {
            this.exitCode = exitCode;
            this.stdout = stdout;
            this.stderr = stderr;
        }

        boolean ok() {
            return exitCode == 0;
        }

        @Override
        public String toString() {
            return "exit=" + exitCode + " stdout=" + stdout.trim() + " stderr=" + stderr.trim();
        }
    }

    private Shell() {
    }

    static Result run(long timeoutMs, String... command) throws IOException, InterruptedException {
        Process process = new ProcessBuilder(command).start();
        process.getOutputStream().close();
        Collector out = new Collector(process.getInputStream());
        Collector err = new Collector(process.getErrorStream());
        out.start();
        err.start();
        try {
            if (!process.waitFor(timeoutMs, TimeUnit.MILLISECONDS)) {
                process.destroyForcibly();
                throw new IOException("command timed out after " + timeoutMs + " ms: " + String.join(" ", command));
            }
            out.join(1000);
            err.join(1000);
            return new Result(process.exitValue(), out.text(), err.text());
        } catch (InterruptedException e) {
            process.destroyForcibly();
            throw e;
        }
    }

    private static final class Collector extends Thread {
        private final InputStream stream;
        private final ByteArrayOutputStream buffer = new ByteArrayOutputStream();

        Collector(InputStream stream) {
            super("m7a-shell-io");
            setDaemon(true);
            this.stream = stream;
        }

        @Override
        public void run() {
            byte[] chunk = new byte[4096];
            try {
                int n;
                while ((n = stream.read(chunk)) >= 0) {
                    synchronized (buffer) {
                        buffer.write(chunk, 0, n);
                    }
                }
            } catch (IOException ignored) {
                // 进程被结束时管道会断开，已经读到的内容照常返回
            }
        }

        String text() {
            synchronized (buffer) {
                return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
            }
        }
    }
}
