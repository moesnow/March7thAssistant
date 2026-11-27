package top.m7a

import android.content.Context
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.URI
import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.util.zip.ZipInputStream
import javax.net.ssl.HttpsURLConnection
import kotlin.coroutines.CoroutineContext

/** 官网维护的兑换码列表，与电脑版 tasks.daily.redemption 读同一份、用同样的地址。 */
internal object RedemptionCodeList {
    private val URLS = listOf(
        "https://m7a.top/assets/config/redemption_codes.json",
        "https://github.kotori.top/https://m7a.top/assets/config/redemption_codes.json",
        "https://raw.githubusercontent.com/moesnow/March7thAssistant/refs/heads/main/assets/config/redemption_codes.json",
    )
    private const val BUNDLED = "assets/config/redemption_codes.json"
    private const val MAX_BYTES = 512 * 1024
    private const val BUDGET_MS = 15_000L

    /** bundled 为 true 表示联网都没成功，用的是安装包自带的列表。 */
    class Latest(val codes: List<String>, val bundled: Boolean)

    /** 依次尝试三个地址，用第一份能读出的列表；都失败时和电脑版一样改用安装包自带的列表。 */
    suspend fun latest(context: Context): Latest = withContext(Dispatchers.IO) {
        val deadline = now() + BUDGET_MS
        for (url in URLS) {
            ensureActive()
            if (now() >= deadline) break
            try {
                return@withContext Latest(validCodes(download(url, deadline, coroutineContext), Instant.now()), bundled = false)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                // 换下一个地址，三个都失败时用安装包里的列表。
            }
        }
        Latest(validCodes(bundled(context), Instant.now()), bundled = true)
    }

    /**
     * 国服还没过期的兑换码，顺序与列表相同。expires_at 为 null 表示不过期，不带时区的按 UTC，读不出的跳过。
     * 整份不是 JSON 数组时抛出异常。
     */
    fun validCodes(json: String, now: Instant): List<String> {
        val items = requireNotNull(Json.decode(json) as? List<*>) { "兑换码列表不是数组" }
        return items.mapNotNull { item ->
            val entry = item as? Map<*, *> ?: return@mapNotNull null
            val code = (entry["code"] as? String)?.takeIf { entry["server"] == "cn" && it.isNotBlank() }
                ?: return@mapNotNull null
            when (val expires = entry["expires_at"]) {
                null -> code
                is String -> code.takeIf { expiry(expires)?.isAfter(now) == true }
                else -> null
            }
        }.distinct()
    }

    private fun expiry(text: String): Instant? = runCatching { OffsetDateTime.parse(text).toInstant() }
        .recoverCatching { LocalDateTime.parse(text).toInstant(ZoneOffset.UTC) }
        .getOrNull()

    private fun download(url: String, deadline: Long, context: CoroutineContext): String {
        val remaining = deadline - now()
        if (remaining <= 0) throw IOException("获取兑换码列表超时")
        val connection = URI(url).toURL().openConnection() as HttpsURLConnection
        try {
            connection.connectTimeout = minOf(5_000L, remaining).toInt()
            connection.readTimeout = minOf(8_000L, remaining).toInt()
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("User-Agent", "March7thAssistant-Android")
            val status = connection.responseCode
            if (status != 200) throw IOException("兑换码列表 HTTP $status")
            // 和电脑版一样只收 JSON 和纯文本，代理出错时常返回网页。
            val type = connection.contentType?.substringBefore(';')?.trim()?.lowercase()
            if (type != null && type !in setOf("application/json", "text/plain")) throw IOException("兑换码列表类型 $type")
            val body = ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(16 * 1024)
                while (true) {
                    context.ensureActive()
                    if (now() >= deadline) throw IOException("获取兑换码列表超时")
                    val size = input.read(buffer)
                    if (size < 0) break
                    if (body.size() + size > MAX_BYTES) throw IOException("兑换码列表过大")
                    body.write(buffer, 0, size)
                }
            }
            return body.toByteArray().decodeToString(throwOnInvalidSequence = true)
        } finally {
            connection.disconnect()
        }
    }

    private fun bundled(context: Context): String = ZipInputStream(context.assets.open("project.zip").buffered()).use { zip ->
        generateSequence { zip.nextEntry }.firstOrNull { it.name == BUNDLED } ?: throw IOException("安装包里没有兑换码列表")
        zip.readBytes().decodeToString()
    }

    private fun now() = System.nanoTime() / 1_000_000
}
