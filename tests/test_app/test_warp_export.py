import pytest
from app.tools.warp_export import srgf_to_uigf_hkrpg, uigf_to_srgf_hkrpg, detect_format


class TestSrgfToUigf:
    def test_basic_conversion(self):
        srgf = {
            "info": {
                "uid": "123456789",
                "lang": "zh-cn",
                "region_time_zone": 8,
                "export_timestamp": 1700000000,
                "export_app": "TestApp",
                "export_app_version": "1.0",
                "srgf_version": "v1.0",
            },
            "list": [
                {
                    "gacha_id": "g1",
                    "gacha_type": "11",
                    "item_id": "i1",
                    "count": "1",
                    "time": "2024-01-01 00:00:00",
                    "name": "Character",
                    "item_type": "角色",
                    "rank_type": "5",
                    "id": "100001",
                }
            ],
        }
        result = srgf_to_uigf_hkrpg(srgf)
        assert result["info"]["version"] == "v4.1"
        assert result["hkrpg"][0]["uid"] == "123456789"
        assert result["hkrpg"][0]["timezone"] == 8
        assert result["hkrpg"][0]["lang"] == "zh-cn"
        assert len(result["hkrpg"][0]["list"]) == 1
        assert result["hkrpg"][0]["list"][0]["name"] == "Character"

    def test_empty_list(self):
        srgf = {"info": {"uid": "1"}, "list": []}
        result = srgf_to_uigf_hkrpg(srgf)
        assert len(result["hkrpg"][0]["list"]) == 0

    def test_missing_info_raises(self):
        with pytest.raises(ValueError, match="Invalid SRGF"):
            srgf_to_uigf_hkrpg({"list": []})

    def test_missing_list_raises(self):
        with pytest.raises(ValueError, match="Invalid SRGF"):
            srgf_to_uigf_hkrpg({"info": {}})

    def test_preserves_all_fields(self):
        srgf = {
            "info": {"uid": "1", "lang": "en", "region_time_zone": 0},
            "list": [{"gacha_id": "g", "gacha_type": "1", "item_id": "i", "count": "1",
                       "time": "t", "name": "n", "item_type": "type", "rank_type": "4", "id": "99"}],
        }
        result = srgf_to_uigf_hkrpg(srgf)
        item = result["hkrpg"][0]["list"][0]
        assert item["gacha_id"] == "g"
        assert item["rank_type"] == "4"
        assert item["id"] == "99"


class TestUigfToSrgf:
    def test_basic_conversion(self):
        uigf = {
            "info": {
                "export_timestamp": 1700000000,
                "export_app": "TestApp",
                "export_app_version": "1.0",
                "version": "v4.1",
            },
            "hkrpg": [
                {
                    "uid": "123456789",
                    "timezone": 8,
                    "lang": "zh-cn",
                    "list": [
                        {
                            "gacha_id": "g1",
                            "gacha_type": "11",
                            "item_id": "i1",
                            "count": "1",
                            "time": "2024-01-01 00:00:00",
                            "name": "Character",
                            "item_type": "角色",
                            "rank_type": "5",
                            "id": "100001",
                        }
                    ],
                }
            ],
        }
        result = uigf_to_srgf_hkrpg(uigf)
        assert result["info"]["uid"] == "123456789"
        assert result["info"]["srgf_version"] == "v1.0"
        assert len(result["list"]) == 1
        assert result["list"][0]["name"] == "Character"

    def test_missing_info_raises(self):
        with pytest.raises(ValueError, match="Invalid UIGF"):
            uigf_to_srgf_hkrpg({"hkrpg": []})

    def test_missing_hkrpg_raises(self):
        with pytest.raises(ValueError, match="Invalid UIGF"):
            uigf_to_srgf_hkrpg({"info": {}})

    def test_empty_list(self):
        uigf = {"info": {}, "hkrpg": [{"uid": "1", "list": []}]}
        result = uigf_to_srgf_hkrpg(uigf)
        assert result["list"] == []

    def test_timezone_conversion(self):
        uigf = {"info": {}, "hkrpg": [{"uid": "1", "timezone": -5, "list": []}]}
        result = uigf_to_srgf_hkrpg(uigf)
        assert result["info"]["region_time_zone"] == -5


class TestFormatRoundtrip:
    def test_srgf_to_uigf_to_srgf(self):
        original = {
            "info": {"uid": "123", "lang": "zh-cn", "region_time_zone": 8},
            "list": [{"gacha_type": "11", "item_id": "i1", "name": "Test", "id": "1"}],
        }
        uigf = srgf_to_uigf_hkrpg(original)
        back = uigf_to_srgf_hkrpg(uigf)
        assert back["info"]["uid"] == original["info"]["uid"]
        assert len(back["list"]) == len(original["list"])
        assert back["list"][0]["name"] == original["list"][0]["name"]


class TestDetectFormat:
    def test_srgf_format(self):
        data = {"info": {"uid": "1"}, "list": []}
        assert detect_format(data) == "srgf"

    def test_uigf_format_hkrpg(self):
        data = {"info": {}, "hkrpg": []}
        assert detect_format(data) == "uigf"

    def test_uigf_format_hk4e(self):
        data = {"info": {}, "hk4e": []}
        assert detect_format(data) == "uigf"

    def test_uigf_format_nap(self):
        data = {"info": {}, "nap": []}
        assert detect_format(data) == "uigf"

    def test_neither_format(self):
        assert detect_format({"foo": "bar"}) == "neither"

    def test_non_dict_returns_neither(self):
        assert detect_format("not a dict") == "neither"
        assert detect_format(None) == "neither"
        assert detect_format(42) == "neither"
        assert detect_format([]) == "neither"

    def test_srgf_with_list_not_list(self):
        # list exists but is not a list type
        data = {"info": {}, "list": "not_a_list"}
        assert detect_format(data) == "neither"
