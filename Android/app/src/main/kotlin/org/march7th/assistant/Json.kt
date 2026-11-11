package org.march7th.assistant

/**
 * 设置、偏好和任务进度用到的最小 JSON 编解码。
 * 不用 org.json：它在 JVM 单测里只是桩，这里的映射需要能直接单测。
 */
internal object Json {
    /** 支持 null、Boolean、Int、Long、Double、String、Map（键为字符串）和 Iterable。 */
    fun encode(value: Any?): String = StringBuilder().also { write(it, value) }.toString()

    /** 整数解析为 Long，带小数点或指数的解析为 Double。格式不对时抛 IllegalArgumentException。 */
    fun decode(text: String): Any? {
        val parser = Parser(text)
        val value = parser.value()
        parser.skipSpace()
        require(parser.done) { "JSON 末尾有多余内容" }
        return value
    }

    private fun write(out: StringBuilder, value: Any?) {
        when (value) {
            null -> out.append("null")
            is Boolean, is Int, is Long -> out.append(value)
            is Double -> {
                require(value.isFinite()) { "JSON 不能表示 $value" }
                out.append(value)
            }
            is String -> writeString(out, value)
            is Map<*, *> -> {
                out.append('{')
                var first = true
                for ((key, item) in value) {
                    if (!first) out.append(',')
                    first = false
                    writeString(out, key as String)
                    out.append(':')
                    write(out, item)
                }
                out.append('}')
            }
            is Iterable<*> -> {
                out.append('[')
                var first = true
                for (item in value) {
                    if (!first) out.append(',')
                    first = false
                    write(out, item)
                }
                out.append(']')
            }
            else -> throw IllegalArgumentException("不支持写成 JSON 的类型：${value::class.java.simpleName}")
        }
    }

    private fun writeString(out: StringBuilder, text: String) {
        out.append('"')
        for (char in text) {
            when (char) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                else -> if (char < ' ') out.append("\\u").append(char.code.toString(16).padStart(4, '0')) else out.append(char)
            }
        }
        out.append('"')
    }

    private class Parser(private val text: String) {
        private var pos = 0
        val done get() = pos == text.length

        fun skipSpace() {
            while (pos < text.length && text[pos] in " \t\r\n") pos++
        }

        fun value(): Any? {
            skipSpace()
            require(pos < text.length) { "JSON 意外结束" }
            return when (text[pos]) {
                '{' -> obj()
                '[' -> array()
                '"' -> string()
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> number()
            }
        }

        private fun obj(): Map<String, Any?> {
            val result = LinkedHashMap<String, Any?>()
            pos++
            skipSpace()
            if (peek() == '}') {
                pos++
                return result
            }
            while (true) {
                skipSpace()
                require(peek() == '"') { "JSON 对象的键应为字符串" }
                val key = string()
                skipSpace()
                expect(':')
                result[key] = value()
                skipSpace()
                if (peek() == ',') {
                    pos++
                } else {
                    expect('}')
                    return result
                }
            }
        }

        private fun array(): List<Any?> {
            val result = ArrayList<Any?>()
            pos++
            skipSpace()
            if (peek() == ']') {
                pos++
                return result
            }
            while (true) {
                result += value()
                skipSpace()
                if (peek() == ',') {
                    pos++
                } else {
                    expect(']')
                    return result
                }
            }
        }

        private fun string(): String {
            val out = StringBuilder()
            pos++
            while (true) {
                require(pos < text.length) { "JSON 字符串没有结束" }
                when (val char = text[pos++]) {
                    '"' -> return out.toString()
                    '\\' -> {
                        require(pos < text.length) { "JSON 转义不完整" }
                        when (val escaped = text[pos++]) {
                            '"', '\\', '/' -> out.append(escaped)
                            'b' -> out.append('\b')
                            'f' -> out.append('\u000C')
                            'n' -> out.append('\n')
                            'r' -> out.append('\r')
                            't' -> out.append('\t')
                            'u' -> {
                                require(pos + 4 <= text.length) { "JSON 转义不完整" }
                                out.append(text.substring(pos, pos + 4).toInt(16).toChar())
                                pos += 4
                            }
                            else -> throw IllegalArgumentException("JSON 转义无效：\\$escaped")
                        }
                    }
                    else -> out.append(char)
                }
            }
        }

        private fun number(): Number {
            val start = pos
            if (peek() == '-') pos++
            while (pos < text.length && (text[pos].isDigit() || text[pos] in ".eE+-")) pos++
            val literal = text.substring(start, pos)
            require(literal.isNotEmpty() && literal != "-") { "JSON 在第 $start 个字符处无法解析" }
            return if (literal.any { it in ".eE" }) literal.toDouble() else literal.toLong()
        }

        private fun literal(word: String, value: Any?): Any? {
            require(text.startsWith(word, pos)) { "JSON 在第 $pos 个字符处无法解析" }
            pos += word.length
            return value
        }

        private fun peek(): Char? = text.getOrNull(pos)

        private fun expect(char: Char) {
            require(peek() == char) { "JSON 在第 $pos 个字符处应为 $char" }
            pos++
        }
    }
}
