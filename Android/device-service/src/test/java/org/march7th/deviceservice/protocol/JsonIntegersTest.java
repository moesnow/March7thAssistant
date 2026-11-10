package org.march7th.deviceservice.protocol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.json.JSONObject;
import org.junit.Test;

public class JsonIntegersTest {
    @Test
    public void displayIdRejectsCoercionAndNarrowing() {
        for (String json : new String[] {
                "0.9", "0.0", "0e0", "4294967296", "\"0\"", "true", "false", "-1", "2147483648",
                "99999999999999999999999999", "null"
        }) {
            Object raw = new JSONObject("{\"id\":" + json + "}").get("id");
            assertThrows(json, IllegalArgumentException.class, () -> JsonIntegers.id(raw, "display_id", Integer.MAX_VALUE));
        }
    }

    @Test
    public void integerDisplayIdsIncludeBothBounds() {
        assertEquals(0, JsonIntegers.id(0, "display_id", Integer.MAX_VALUE));
        assertEquals(Integer.MAX_VALUE, JsonIntegers.id((long) Integer.MAX_VALUE, "display_id", Integer.MAX_VALUE));
    }

    @Test
    public void pointerIdUsesTheSameStrictTypeWithItsOwnBounds() {
        assertEquals(9, JsonIntegers.id(9, "pointer_id", 9));
        for (Object raw : new Object[] {null, false, "0", 0.1, 10, -1, 4294967296L}) {
            assertThrows(IllegalArgumentException.class, () -> JsonIntegers.id(raw, "pointer_id", 9));
        }
    }
}
