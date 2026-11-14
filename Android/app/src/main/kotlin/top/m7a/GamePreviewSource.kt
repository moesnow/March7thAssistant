package top.m7a

import android.graphics.Bitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.march7th.deviceservice.protocol.Message
import org.march7th.deviceservice.protocol.MessageCodec
import org.march7th.deviceservice.protocol.Protocol
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer

/** 每轮任务的预览地址和令牌只在内存里保留。 */
internal class GamePreviewSource(private val port: Int, private val token: String) {
    suspend fun collectFrames(displayId: Int, onFrame: suspend (Bitmap) -> Unit) = withContext(Dispatchers.IO) {
        Socket().use { socket ->
            socket.connect(InetSocketAddress("127.0.0.1", port), 1000)
            socket.soTimeout = 1000
            socket.tcpNoDelay = true
            val input = socket.getInputStream().buffered()
            val output = socket.getOutputStream()
            val hello = JSONObject()
                .put("cmd", "hello").put("protocol", Protocol.VERSION).put("token", token)
            MessageCodec.write(output, Message(hello))
            if (MessageCodec.read(input, Protocol.MAX_HANDSHAKE_HEADER_BYTES, 0)?.header?.optBoolean("ok") != true) {
                throw IOException("Game preview handshake failed")
            }
            val request = JSONObject().put("cmd", "preview_frame").put("display_id", displayId)
            var sequence = 0L
            while (currentCoroutineContext().isActive) {
                request.put("after_seq", sequence)
                MessageCodec.write(output, Message(request))
                val reply = MessageCodec.read(input, Protocol.MAX_HANDSHAKE_HEADER_BYTES, Protocol.PREVIEW_MAX_BYTES)
                    ?: throw IOException("Game preview disconnected")
                if (!reply.header.optBoolean("ok")) throw IOException("Game preview request failed")
                if (reply.payloadLength > 0) {
                    val width = reply.header.optInt("width")
                    val height = reply.header.optInt("height")
                    val received = reply.header.optLong("seq")
                    if (width !in 1..Protocol.PREVIEW_WIDTH || height !in 1..Protocol.PREVIEW_HEIGHT ||
                        reply.payloadLength != width * height * 4 || received <= sequence
                    ) {
                        throw IOException("Invalid game preview frame")
                    }
                    sequence = received
                    val frame = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888).apply {
                        setHasAlpha(false)
                        copyPixelsFromBuffer(ByteBuffer.wrap(reply.payload))
                    }
                    onFrame(frame)
                }
                delay(Protocol.PREVIEW_INTERVAL_MS.toLong())
            }
        }
    }
}
