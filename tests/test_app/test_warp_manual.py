from copy import deepcopy
import json
import subprocess
import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import QLockFile

from app.tools.warp_manual import (MANUAL_KEY, empty_manual, new_entry, manual_data,
                                   pool_summary, gold_rows, record_identity,
                                   standard_data, backup_data, display_history)
from app.tools.warp_import import (normalize, prepare_import, save_import, read_snapshot,
                                   edit_plan, clear_plan, save_export)
from app.tools.warp_export import WarpExport, WarpThread, WarpStatus, srgf_to_uigf_hkrpg
from app.tools.warp_excel import export_excel
from tests.test_app.test_warp_import import data, put


def sample():
    result = data(range(1, 9))
    for index in (1, 5):
        result['list'][index]['rank_type'] = '5'
        result['list'][index]['name'] = '布洛妮娅'
    result[MANUAL_KEY] = empty_manual()
    return result


def manual_sample():
    result = sample()
    result[MANUAL_KEY]['entries'] = [new_entry('11', '希儿', 78), new_entry('11', '景元')]
    record = result['list'][1]
    result[MANUAL_KEY]['corrections'][record['id']] = {'record': record_identity(record), 'pity': 75}
    return result


def test_manual_never_fabricates_records():
    result = data(())
    result[MANUAL_KEY] = dict(empty_manual(), entries=[new_entry('11', '希儿', 78)])
    normalized = normalize(result)
    assert normalized['list'] == []
    assert set(manual_data(normalized)['entries'][0]) == {'key', 'pool', 'name', 'pity', 'date'}
    assert manual_data(normalized)['entries'][0]['date'] is None
    assert srgf_to_uigf_hkrpg(standard_data(normalized))['hkrpg'][0]['list'] == []


def test_original_record_counts_and_explicit_unknown_average():
    result = sample()
    stats = pool_summary(result, '11')
    assert [row['observed'] for row in stats['golds']] == [2, 4]
    assert [row['pity'] for row in stats['golds']] == [2, 4]
    assert (stats['known'], stats['unknown'], stats['average'], stats['since']) == (2, 0, 3, 2)
    stats = pool_summary(manual_sample(), '11')
    assert (stats['known'], stats['unknown']) == (3, 1)
    assert stats['average'] is None
    assert len(stats['records']) == 8


def test_no_gold_no_division_and_unproven_current_pity():
    result = data()
    stats = pool_summary(result, '11')
    assert stats['average'] is None and stats['since_bounded'] and stats['since'] == 2
    html = WarpExport(result).data_to_html()
    assert '≥' not in html and '?' not in html
    assert '一共' in html and '已累计' in html
    assert pool_summary(data(()), '11')['average'] is None


def test_correction_is_overlay_and_can_be_unknown():
    result = manual_sample()
    raw = deepcopy(result['list'])
    result[MANUAL_KEY]['corrections']['2']['pity'] = None
    assert gold_rows(result)[0]['pity'] is None
    assert gold_rows(result)[0]['corrected']
    del result[MANUAL_KEY]['corrections']['2']
    assert not gold_rows(result)[0]['corrected']
    assert result['list'] == raw


@pytest.mark.parametrize('change', ['name', 'gacha_type', 'time', 'missing'])
def test_correction_does_not_attach_to_changed_record(change):
    result = manual_sample()
    if change == 'missing':
        result['list'].pop(1)
    else:
        result['list'][1][change] = {'name': '不同物品', 'gacha_type': '12', 'time': '2024-01-01 00:00:00'}[change]
    rows = gold_rows(result, include_orphans=True)
    assert sum(row['orphan'] for row in rows) == 1
    assert not any(row['corrected'] for row in rows if not row['orphan'])


def test_optional_enrichment_preserves_correction():
    result = manual_sample()
    result['list'][1]['item_id'] = '1101'
    assert gold_rows(result)[0]['pity'] == 75


@pytest.mark.parametrize('field,value', [('pool', '999'), ('name', ''), ('pity', 0),
                                        ('pity', True), ('pity', '20'), ('pity', -1),
                                        ('date', '2024-02-30'), ('date', '20240101'),
                                        ('date', 123)])
def test_invalid_manual_entry(field, value):
    result = manual_sample()
    result[MANUAL_KEY]['entries'][0][field] = value
    with pytest.raises(ValueError):
        normalize(result)


@pytest.mark.parametrize('bad', [None, [], {'version': 2}, {'version': True, 'entries': [], 'corrections': {}}])
def test_invalid_extension(bad):
    result = sample()
    result[MANUAL_KEY] = bad
    with pytest.raises(ValueError):
        normalize(result)


def test_backup_roundtrip_and_standard_exclusion(tmp_path):
    result = manual_sample()
    source = put(tmp_path / 'backup.json', backup_data(result))
    target = tmp_path / 'warp.json'
    save_import(prepare_import(source, target))
    assert json.loads(target.read_bytes()) == result
    save_import(prepare_import(source, target))
    assert json.loads(target.read_bytes()) == result
    assert MANUAL_KEY not in standard_data(result)


def test_merge_does_not_guess_manual_duplicates(tmp_path):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    incoming = data((99,))
    incoming['list'][0].update(name='希儿', rank_type='5')
    source = put(tmp_path / 'source.json', incoming)
    plan = prepare_import(source, target)
    assert manual_data(plan.data) == manual_data(result)
    assert len(plan.data['list']) == 9
    incoming[MANUAL_KEY] = dict(empty_manual(), entries=[new_entry('11', '希儿', 78)])
    put(source, backup_data(incoming))
    assert len(manual_data(prepare_import(source, target).data)['entries']) == 3


def test_conflicting_annotation_versions_rejected(tmp_path):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    incoming = deepcopy(result)
    incoming[MANUAL_KEY]['entries'][0]['pity'] = 79
    source = put(tmp_path / 'source.json', backup_data(incoming))
    with pytest.raises(ValueError, match='不同版本'):
        prepare_import(source, target)
    assert prepare_import(source, target, mode='replace').data == incoming


def test_manual_only_import_account_guard_and_locale_adoption(tmp_path):
    result = manual_sample(); result['list'] = []
    result[MANUAL_KEY]['corrections'] = {}
    target = put(tmp_path / 'warp.json', result)
    source = put(tmp_path / 'source.json', data(uid='200000002'))
    with pytest.raises(ValueError, match='账号不一致'):
        prepare_import(source, target)
    incoming = data(); incoming['info'].update(lang='en-us', region_time_zone=-5)
    put(source, incoming)
    plan = prepare_import(source, target)
    assert plan.existing_manual_count == 2
    assert plan.data['info']['lang'] == 'en-us'
    assert manual_data(plan.data) == manual_data(result)


def test_replace_drops_manual_but_backup_restores_everything(tmp_path):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    before = target.read_bytes()
    source = put(tmp_path / 'source.json', data(uid='200000002'))
    plan = prepare_import(source, target, mode='replace')
    assert plan.existing_manual_count == 3
    backup = save_import(plan)
    assert backup.read_bytes() == before
    assert MANUAL_KEY not in json.loads(target.read_bytes())
    save_import(prepare_import(backup, target, mode='replace'))
    assert json.loads(target.read_bytes()) == result


def test_clear_backup_and_stale_update_cannot_resurrect(tmp_path):
    result = manual_sample()
    target = put(tmp_path / 'warp.json', result)
    original, data_ = read_snapshot(target)
    stale = edit_plan(data_, original, target)
    backup = save_import(clear_plan(data_, original, target))
    cleared = json.loads(target.read_bytes())
    assert cleared['list'] == [] and MANUAL_KEY not in cleared
    assert cleared['march7th_cleared']
    assert backup.read_bytes() == original
    with pytest.raises(ValueError, match='发生变化'):
        save_import(stale)
    source = put(tmp_path / 'new.json', data(uid='200000002'))
    save_import(prepare_import(source, target))
    assert read_snapshot(target)[1]['info']['uid'] == '200000002'


def test_two_editors_reject_stale_snapshot(tmp_path):
    target = put(tmp_path / 'warp.json', sample())
    original, result = read_snapshot(target)
    first = edit_plan(result, original, target)
    result[MANUAL_KEY]['entries'].append(new_entry('11', '希儿', 78))
    save_import(edit_plan(result, original, target))
    with pytest.raises(ValueError, match='发生变化'):
        save_import(first)
    assert read_snapshot(target)[1][MANUAL_KEY]['entries'][0]['name'] == '希儿'


def test_cross_process_lock(tmp_path):
    target = put(tmp_path / 'warp.json', sample())
    original, result = read_snapshot(target)
    lock = QLockFile(str(target.resolve()) + '.lock')
    assert lock.tryLock(0)
    try:
        code = ('from app.tools.warp_import import read_snapshot, edit_plan, save_import; '
                f'p={str(target)!r}; original,data=read_snapshot(p); save_import(edit_plan(data,original,p))')
        proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=20)
        assert proc.returncode != 0 and '正在保存' in proc.stderr
        assert target.read_bytes() == original
    finally:
        lock.unlock()
    save_import(edit_plan(result, original, target))


@pytest.mark.parametrize('mode', ['normal', 'full'])
def test_fetch_preserves_manual_and_account(mode, monkeypatch):
    result = manual_sample()
    warp = WarpExport(result)
    monkeypatch.setattr(warp, 'get_gacha_logs', lambda *a: [] if a[1] != '11' else data((9,))['list'])
    assert warp.fetch_data('test', 'test', mode)
    assert manual_data(warp.export_data()) == manual_data(result)
    assert warp.export_data()['list'][-1]['id'] == '9'
    assert not warp.init_info({'list': [{'uid': '999', 'lang': 'zh-cn'}], 'region_time_zone': 8})


def test_worker_does_not_overwrite_concurrent_manual_edit(tmp_path, monkeypatch, qapp):
    monkeypatch.chdir(tmp_path)
    target = put(tmp_path / 'warp.json', sample())
    monkeypatch.setattr(WarpExport, 'get_url', lambda self: 'https://example.test/?test=1')
    def fetch(self, *_):
        original, result = read_snapshot()
        result[MANUAL_KEY]['entries'].append(new_entry('11', '希儿', 78))
        save_import(edit_plan(result, original))
        self.warplink = 'test'
        return True
    monkeypatch.setattr(WarpExport, 'fetch_data', fetch)
    worker = WarpThread(None)
    statuses = []
    worker.warpSignal.connect(statuses.append)
    worker.run()
    assert statuses == [WarpStatus.FAILURE]
    assert read_snapshot(target)[1][MANUAL_KEY]['entries'][0]['name'] == '希儿'


def test_corrupt_file_not_overwritten_by_fetch(tmp_path, monkeypatch, qapp):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / 'warp.json'; target.write_bytes(b'{broken')
    worker = WarpThread(None)
    statuses = []
    worker.warpSignal.connect(statuses.append)
    worker.run()
    assert statuses == [WarpStatus.FAILURE] and target.read_bytes() == b'{broken'


def test_excel_shares_mean_unknowns_and_original_detail(tmp_path):
    from openpyxl import load_workbook
    result = manual_sample()
    result[MANUAL_KEY]['entries'][0]['name'] = '=1+1'
    path = tmp_path / 'warps.xlsx'
    export_excel(result, path)
    wb = load_workbook(path)
    assert wb.worksheets[0].max_row == 9
    assert wb.worksheets[0]['G3'].value == 2
    assert wb.worksheets[1]['E2'].value == 75
    assert wb.worksheets[1]['C4'].value is None
    assert wb.worksheets[1]['E5'].value is None
    assert wb.worksheets[1]['B4'].data_type == 's'
    assert wb.worksheets[2]['F5'].value is None
    html = WarpExport(result).data_to_html()
    assert '52.33' not in html and ">?</font>" in html
    result[MANUAL_KEY]['entries'].pop()
    export_excel(result, path)
    assert load_workbook(path).worksheets[2]['F5'].value == pytest.approx(pool_summary(result, '11')['average'])


def test_compact_history_combines_manual_and_real_without_source_labels():
    result = manual_sample()
    before = deepcopy(result)
    html = WarpExport(result).data_to_html()
    assert html.count('5星历史记录') == 1
    assert '希儿[78]' in html and '景元[?]' in html
    assert '布洛妮娅[75]' in html and '布洛妮娅[4]' in html
    assert html.index('希儿[78]') < html.index('景元[?]') < html.index('布洛妮娅[75]')
    for clutter in ('手填', '手动补充', '时间未知', '抽数不明', '仅统计', '历史可能不完整'):
        assert clutter not in html
    assert '52.33' not in html and ">?</font>" in html
    assert '5星明细: 2 [25.00%]' in html
    assert '抽卡明细' not in html
    assert '5星历史记录:' in html and '含补充' not in html
    assert '<sup>*</sup>' not in html
    assert result == before


def test_display_history_sorts_known_dates_and_keeps_unknown_manual_order():
    result = sample()
    result['list'][1]['name'] = '真实一'; result['list'][1]['time'] = '2024-02-01 12:00:00'
    result['list'][5]['name'] = '真实二'; result['list'][5]['time'] = '2024-04-01 12:00:00'
    result[MANUAL_KEY]['entries'] = [
        new_entry('11', '日期较晚', 70, '2024-05-01'),
        new_entry('11', '未知一', 78),
        new_entry('11', '日期居中', 65, '2024-03-01'),
        new_entry('11', '未知二'),
        new_entry('11', '同日一', 75, '2024-02-01'),
        new_entry('11', '同日二', 74, '2024-02-01'),
        new_entry('12', '其他池', 60),
    ]
    original = deepcopy(result)
    rows = display_history(pool_summary(result, '11'))
    assert [r['name'] for r in rows] == ['未知一', '未知二', '同日一', '同日二', '真实一', '日期居中', '真实二', '日期较晚']
    assert result == original
    result[MANUAL_KEY]['entries'][1], result[MANUAL_KEY]['entries'][3] = (
        result[MANUAL_KEY]['entries'][3], result[MANUAL_KEY]['entries'][1])
    assert [r['name'] for r in display_history(pool_summary(result, '11'))][:2] == ['未知二', '未知一']


def test_without_manual_history_keeps_original_id_order_even_with_unusual_dates():
    result = sample()
    result['list'][1].update(name='先记录', time='2024-05-01 12:00:00')
    result['list'][5].update(name='后记录', time='2024-04-01 12:00:00')
    assert [r['name'] for r in display_history(pool_summary(result, '11'))] == ['先记录', '后记录']


def test_compact_history_uses_original_counts_until_user_corrects_them():
    result = sample()
    html = WarpExport(result).data_to_html()
    assert '布洛妮娅[2]' in html and '3.00' in html
    assert '≥' not in html and '（已知）' not in html and '?' not in html
    assert '5星: 2 [25.00%]' in html and '抽卡明细' not in html
    assert '5星历史记录:' in html and '含补充' not in html
    record = result['list'][1]
    result[MANUAL_KEY]['corrections'][record['id']] = {'record': record_identity(record), 'pity': 72}
    html = WarpExport(result).data_to_html()
    assert '布洛妮娅[72]' in html and '38.00' in html
    assert '≥' not in html and '（已知）' not in html
    result[MANUAL_KEY]['corrections'][record['id']]['pity'] = None
    html = WarpExport(result).data_to_html()
    assert '布洛妮娅[?]' in html and '≥' not in html and ">?</font>" in html


def test_manual_only_unknown_average_uses_short_placeholder_not_zero():
    result = data(())
    result[MANUAL_KEY] = dict(empty_manual(), entries=[new_entry('11', '希儿'), new_entry('11', '景元')])
    html = WarpExport(result).data_to_html()
    assert html.count('5星历史记录') == 1
    assert '希儿[?]' in html and '景元[?]' in html
    assert ">?</font>" in html
    assert '0.00' not in html and '<sup>*</sup>' not in html
    assert '手动补充' not in html and '时间未知' not in html


def test_known_manual_counts_keep_original_average_title_and_exact_detail_rates():
    result = manual_sample()
    result[MANUAL_KEY]['entries'].pop()
    html = WarpExport(result).data_to_html()
    assert '抽卡明细' not in html
    assert '5星明细: 2 [25.00%]' in html
    assert '4星: 6 [75.00%]' in html
    assert '3星: 0 [0.00%]' in html
    assert '52.33' in html and '五星平均出货次数为' in html
    assert '（已知）' not in html and '<sup>*</sup>' not in html
    assert '希儿[78]' in html and '布洛妮娅[75]' in html and '布洛妮娅[4]' in html


@pytest.mark.parametrize('pool', ['11', '12', '21', '22', '1', '2'])
def test_no_handwritten_data_preserves_original_counts_mean_and_labels(pool):
    result = sample()
    del result[MANUAL_KEY]
    for record in result['list']:
        record['gacha_type'] = pool
    stats = pool_summary(result, pool)
    assert [r['pity'] for r in stats['golds']] == [2, 4]
    assert stats['average'] == 3 and stats['since'] == 2
    html = WarpExport(result).data_to_html()
    assert '布洛妮娅[2]' in html and '布洛妮娅[4]' in html
    assert "五星平均出货次数为: <font color='green'>3.00</font>" in html
    assert "一共 <font color='DeepSkyBlue'>8</font> 抽 已累计 <font color='LimeGreen'>2</font> 抽未出5星" in html
    assert '5星: 2 [25.00%]' in html and '4星: 6 [75.00%]' in html
    for added_text in ('≥', '?', '已知', '抽卡明细', '5星明细', '手填', '明细共'):
        assert added_text not in html


def test_manual_only_known_values_are_used_without_inventing_details():
    result = data(())
    result[MANUAL_KEY] = dict(empty_manual(), entries=[new_entry('11', '希儿', 70), new_entry('11', '景元', 80)])
    original = deepcopy(result)
    assert pool_summary(result, '11')['average'] == 75
    html = WarpExport(result).data_to_html()
    assert '希儿[70]' in html and '景元[80]' in html and '75.00' in html
    assert '%' not in html and '≥' not in html and '?' not in html
    assert result == original and result['list'] == []


def test_html_escapes_manual_and_real_names():
    result = manual_sample()
    result['list'][1]['name'] = '<img src="file:///private">'
    result[MANUAL_KEY]['entries'][0]['name'] = '<script>alert(1)</script>'
    html = WarpExport(result).data_to_html()
    assert '<script>' not in html and '<img ' not in html
    assert '&lt;script&gt;' in html


def test_backup_export_failure_preserves_existing_backup(tmp_path):
    target = put(tmp_path / 'existing.m7backup.json', backup_data(manual_sample()))
    original = target.read_bytes()
    with patch('app.tools.warp_import.os.replace', side_effect=OSError('disk error')):
        with pytest.raises(OSError):
            save_export(backup_data(sample()), target)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob('*.tmp'))


def test_names_cannot_load_images_or_create_markdown_links():
    result = manual_sample()
    result['list'][1]['name'] = '![image](file:///private.png)'
    result[MANUAL_KEY]['entries'][0]['name'] = '[click](https://example.test/)'
    html = WarpExport(result).data_to_html()
    assert '<img ' not in html and '<a ' not in html


def test_full_update_marks_missing_correction_inactive(monkeypatch):
    result = manual_sample()
    warp = WarpExport(result)
    replacement = data((1, 3, 4, 5, 6, 7, 8))['list']
    monkeypatch.setattr(warp, 'get_gacha_logs', lambda *a: replacement if a[1] == '11' else [])
    assert warp.fetch_data('test', 'test', 'full')
    exported = warp.export_data()
    assert len(manual_data(exported)['entries']) == 2
    assert '2' in manual_data(exported)['corrections']
    assert sum(row['orphan'] for row in gold_rows(exported, include_orphans=True)) == 1
