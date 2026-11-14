package top.m7a.ui

import java.math.BigInteger

private val versionPattern = Regex(
    """v?(?:([0-9]+)!)?([0-9]+(?:\.[0-9]+)*)
        (?:[-_.]*(alpha|a|beta|b|preview|pre|rc|c)[-_.]*([0-9]+)?)?
        (?:-([0-9]+)|[-_.]*(post|rev|r)[-_.]*([0-9]+)?)?
        (?:[-_.]*(dev)[-_.]*([0-9]+)?)?
        (?:\+([a-z0-9]+(?:[-_.][a-z0-9]+)*))?""",
    setOf(RegexOption.IGNORE_CASE, RegexOption.COMMENTS),
)

/** 与桌面 utils.version.Version 的严格解析和排序一致。 */
@ConsistentCopyVisibility
internal data class UpdateVersion private constructor(
    val epoch: BigInteger,
    val numbers: List<BigInteger>,
    val pre: Int,
    val preNumber: BigInteger,
    val post: BigInteger?,
    val dev: BigInteger?,
    val local: Boolean,
) : Comparable<UpdateVersion> {
    val isPrerelease: Boolean get() = pre < FINAL || dev != null

    override fun compareTo(other: UpdateVersion): Int {
        val epochOrder = epoch.compareTo(other.epoch)
        if (epochOrder != 0) return epochOrder
        for (index in 0 until minOf(numbers.size, other.numbers.size)) {
            val numberOrder = numbers[index].compareTo(other.numbers[index])
            if (numberOrder != 0) return numberOrder
        }
        val lengthOrder = numbers.size.compareTo(other.numbers.size)
        if (lengthOrder != 0) return lengthOrder
        return compareValuesBy(this, other, { it.pre }, { it.preNumber }, { it.post }, { it.dev == null }, { it.dev }, { it.local })
    }

    companion object {
        private const val FINAL = 3

        fun parse(text: String): UpdateVersion? {
            val match = versionPattern.matchEntire(text.trim()) ?: return null
            val (epoch, release, pre, preNumber, implicitPost, postLabel, postNumber, devLabel, devNumber, local) = match.destructured
            val post = when {
                implicitPost.isNotEmpty() -> implicitPost.toBigInteger()
                postLabel.isNotEmpty() -> postNumber.toBigIntegerOrNull() ?: BigInteger.ZERO
                else -> null
            }
            val dev = devNumber.toBigIntegerOrNull() ?: BigInteger.ZERO.takeIf { devLabel.isNotEmpty() }
            val preOrder = when (pre.lowercase()) {
                "a", "alpha" -> 0
                "b", "beta" -> 1
                "c", "rc", "pre", "preview" -> 2
                else -> if (post == null && dev != null) -1 else FINAL
            }
            return UpdateVersion(
                epoch.toBigIntegerOrNull() ?: BigInteger.ZERO,
                release.split('.').map(String::toBigInteger).dropLastWhile { it == BigInteger.ZERO },
                preOrder, preNumber.toBigIntegerOrNull() ?: BigInteger.ZERO, post, dev, local.isNotEmpty(),
            )
        }
    }
}
