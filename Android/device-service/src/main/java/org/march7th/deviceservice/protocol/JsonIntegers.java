package org.march7th.deviceservice.protocol;

/** 校验 JSON 解析后的原始值，避免 org.json 把小数、字符串或溢出的数值强制转成 ID。 */
public final class JsonIntegers {
    private JsonIntegers() {
    }

    public static long integer(Object value, String field) {
        if (value instanceof Integer || value instanceof Long) {
            return ((Number) value).longValue();
        }
        throw new IllegalArgumentException(field + " must be a JSON integer");
    }

    public static int id(Object value, String field, int max) {
        long id = integer(value, field);
        if (id < 0 || id > max) {
            throw new IllegalArgumentException(field + " must be 0.." + max);
        }
        return (int) id;
    }
}
