"""Five-star summaries are annotations, never fabricated individual warp records.

The extension lives in the same atomic document as the real records and inherits
its account. Entry keys identify annotations only; they are NOT game record IDs.
"""
from copy import deepcopy
from datetime import date
from uuid import uuid4

from module.localization import tr

MANUAL_KEY = 'march7th_manual'
BACKUP_FORMAT = 'March7thAssistant.WarpBackup'
POOLS = ('11', '12', '21', '22', '1', '2')


def pool_names():
    return dict(zip(POOLS, (tr('角色活动跃迁'), tr('光锥活动跃迁'),
                           tr('Fate[UBW]角色联动跃迁'), tr('Fate[UBW]光锥联动跃迁'),
                           tr('常驻跃迁'), tr('新手跃迁'))))


def empty_manual():
    return {'version': 1, 'entries': [], 'corrections': {}}


def manual_data(data):
    return data.get(MANUAL_KEY, empty_manual())


def manual_count(data):
    manual = manual_data(data)
    return len(manual['entries']) + len(manual['corrections'])


def validate_pity(value):
    if value is not None and (type(value) is not int or not 1 <= value <= 1000000):
        raise ValueError(tr('抽数请填写正整数，或保留为未知。'))


def validate_manual(data):
    manual = manual_data(data)
    if (not isinstance(manual, dict) or type(manual.get('version')) is not int
            or manual['version'] != 1 or not isinstance(manual.get('entries'), list)
            or not isinstance(manual.get('corrections'), dict)):
        raise ValueError(tr('手工数据格式无效或版本不受支持。'))
    keys = set()
    for entry in manual['entries']:
        if not isinstance(entry, dict):
            raise ValueError(tr('手工数据格式无效或版本不受支持。'))
        key = entry.get('key')
        if not isinstance(key, str) or not key or key in keys:
            raise ValueError(tr('手工数据格式无效或版本不受支持。'))
        keys.add(key)
        if entry.get('pool') not in POOLS or not isinstance(entry.get('name'), str) or not entry['name'].strip():
            raise ValueError(tr('请选择卡池并填写五星物品名称。'))
        validate_pity(entry.get('pity'))
        if entry.get('date') is not None:
            try:
                if date.fromisoformat(entry['date']).isoformat() != entry['date']:
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValueError(tr('时间请填写 YYYY-MM-DD，或留空表示未知。')) from exc
    for key, correction in manual['corrections'].items():
        if (not isinstance(key, str) or not key.isascii() or not key.isdigit()
                or not isinstance(correction, dict) or not isinstance(correction.get('record'), dict)):
            raise ValueError(tr('手工数据格式无效或版本不受支持。'))
        record = correction['record']
        if (record.get('id') != key or record.get('gacha_type') not in POOLS
                or record.get('rank_type') != '5'
                or not all(isinstance(record.get(k), str) and record[k] for k in ('name', 'time'))):
            raise ValueError(tr('手工数据格式无效或版本不受支持。'))
        validate_pity(correction.get('pity'))
    return data


def new_entry(pool, name, pity=None, day=None):
    entry = {'key': str(uuid4()), 'pool': pool, 'name': name.strip(), 'pity': pity, 'date': day or None}
    validate_manual({MANUAL_KEY: dict(empty_manual(), entries=[entry])})
    return entry


def record_identity(record):
    # Optional fields can later be enriched. Match the actual immutable record,
    # never match a manual summary to a real record just because names coincide.
    return {key: record[key] for key in ('id', 'gacha_type', 'rank_type', 'name', 'time')}


def merge_manual(existing, incoming):
    result = deepcopy(manual_data(existing))
    entries = {entry['key']: entry for entry in result['entries']}
    for entry in manual_data(incoming)['entries']:
        if entry['key'] in entries:
            if entries[entry['key']] != entry:
                raise ValueError(tr('手工数据存在不同版本，请选择替换或使用其他备份。'))
        else:
            result['entries'].append(deepcopy(entry))
            entries[entry['key']] = entry
    for key, value in manual_data(incoming)['corrections'].items():
        if key in result['corrections'] and result['corrections'][key] != value:
            raise ValueError(tr('手工数据存在不同版本，请选择替换或使用其他备份。'))
        result['corrections'][key] = deepcopy(value)
    return result


def gold_rows(data, include_orphans=False):
    """Shared by HTML, correction editor and Excel. First observed span is a
    lower bound, not an exact pity: imported/fetched history can be truncated.
    Later spans are counts within the saved detail, not proof of completeness.
    """
    counters, seen, rows, matched = {}, set(), [], set()
    corrections = manual_data(data)['corrections']
    for record in sorted(data['list'], key=lambda r: int(r['id'])):
        pool = record['gacha_type']
        counters[pool] = counters.get(pool, 0) + 1
        if record['rank_type'] != '5':
            continue
        correction = corrections.get(record['id'])
        active = correction is not None and correction['record'] == record_identity(record)
        if active:
            matched.add(record['id'])
        rows.append({'record': record, 'observed': counters[pool], 'bounded': pool not in seen,
                     'pity': correction['pity'] if active else (counters[pool] if pool in seen else None),
                     'corrected': active, 'orphan': False})
        counters[pool] = 0
        seen.add(pool)
    if include_orphans:
        for key in sorted(corrections.keys() - matched, key=int):
            rows.append({'record': corrections[key]['record'], 'observed': None, 'bounded': True,
                         'pity': corrections[key]['pity'], 'corrected': True, 'orphan': True})
    return rows


def pool_summary(data, pool):
    records = sorted((r for r in data['list'] if r['gacha_type'] == pool), key=lambda r: int(r['id']))
    golds = [r for r in gold_rows(data) if r['record']['gacha_type'] == pool]
    entries = [entry for entry in manual_data(data)['entries'] if entry['pool'] == pool]
    values = [row['pity'] for row in golds] + [entry['pity'] for entry in entries]
    known = [value for value in values if value is not None]
    since = 0
    for record in reversed(records):
        if record['rank_type'] == '5':
            break
        since += 1
    return {'records': records, 'golds': golds, 'entries': entries, 'known': len(known),
            'unknown': len(values) - len(known), 'average': sum(known) / len(known) if known else None,
            'since': since, 'since_bounded': not golds}


def standard_data(data):
    """Only real individual records belong in UIGF/SRGF."""
    return deepcopy({'info': data['info'], 'list': data['list']})


def backup_data(data):
    return {'format': BACKUP_FORMAT, 'version': 1, 'data': deepcopy(data)}
