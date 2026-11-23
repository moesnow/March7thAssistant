"""SRGF / UIGF conversion shared with the original export page."""


def srgf_to_uigf_hkrpg(srgf: dict) -> dict:
    if "info" not in srgf or "list" not in srgf:
        raise ValueError("Invalid SRGF input")

    info = srgf["info"]
    raw_list = srgf["list"]

    uigf = {
        "info": {
            "export_timestamp": info.get("export_timestamp"),
            "export_app": info.get("export_app", "Unknown App"),
            "export_app_version": info.get("export_app_version", ""),
            "version": "v4.1"
        },
        "hkrpg": [
            {
                "uid": info.get("uid"),
                "timezone": int(info.get("region_time_zone", 0)),
                "lang": info.get("lang", "zh-cn"),
                "list": []
            }
        ]
    }

    for item in raw_list:
        record = {
            "gacha_id": item.get("gacha_id"),
            "gacha_type": item.get("gacha_type"),
            "item_id": item.get("item_id"),
            "count": item.get("count", "1"),
            "time": item.get("time"),
            "name": item.get("name"),
            "item_type": item.get("item_type"),
            "rank_type": item.get("rank_type"),
            "id": item.get("id")
        }
        uigf["hkrpg"][0]["list"].append(record)

    return uigf


def uigf_to_srgf_hkrpg(uigf: dict) -> dict:
    if "info" not in uigf or "hkrpg" not in uigf:
        raise ValueError("Invalid UIGF input")

    info = uigf["info"]
    first_entry = uigf["hkrpg"][0]  # UIGF 支持多个 UID，但 SRGF 只支持单 UID

    srgf = {
        "info": {
            "uid": first_entry.get("uid"),
            "lang": first_entry.get("lang", "zh-cn"),
            "region_time_zone": first_entry.get("timezone", 0),
            "export_timestamp": info.get("export_timestamp"),
            "export_app": info.get("export_app"),
            "export_app_version": info.get("export_app_version"),
            "srgf_version": "v1.0"
        },
        "list": []
    }

    for item in first_entry.get("list", []):
        record = {
            "gacha_id": item.get("gacha_id"),
            "gacha_type": item.get("gacha_type"),
            "item_id": item.get("item_id"),
            "count": item.get("count", "1"),
            "time": item.get("time"),
            "name": item.get("name"),
            "item_type": item.get("item_type"),
            "rank_type": item.get("rank_type"),
            "id": item.get("id")
        }
        srgf["list"].append(record)

    return srgf


def detect_format(data: dict) -> str:
    if not isinstance(data, dict):
        return "neither"

    # SRGF
    if "info" in data and "list" in data and isinstance(data.get("list"), list):
        return "srgf"

    # UIGF
    if "info" in data and any(k in data for k in ("hkrpg", "hk4e", "nap")):
        return "uigf"

    return "neither"
