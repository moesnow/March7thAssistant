from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from app.tools.warp_import import prepare_import, save_import, WarpImportError, normalize


def data(ids=(1, 2), uid='100000001'):
    return {'info': {'uid': uid, 'lang': 'zh-cn', 'region_time_zone': 8, 'srgf_version': 'v1.0'},
            'list': [{'id': str(i), 'gacha_type': '11', 'rank_type': '4', 'name': '三月七',
                      'item_type': '角色', 'time': '2026-11-13 12:00:00'} for i in ids]}


def put(path, content):
    path.write_text(json.dumps(content, ensure_ascii=False), encoding='utf-8')
    return path


@pytest.fixture
def files(tmp_path):
    return put(tmp_path / 'import.json', data((2, 3))), put(tmp_path / 'warp.json', data())


def test_merge_and_exact_backup(files):
    source, target = files
    before = target.read_bytes()
    plan = prepare_import(source, target)
    assert (plan.existing_count, plan.incoming_count, plan.added_count, plan.duplicate_count) == (2, 2, 1, 1)
    backup = save_import(plan)
    assert backup.read_bytes() == before
    assert [r['id'] for r in json.loads(target.read_bytes())['list']] == ['1', '2', '3']
    assert not list(target.parent.glob('*.tmp'))


def test_first_import_and_repeat(tmp_path):
    source = put(tmp_path / 'input.json', data((1, 1, 2)))
    target = tmp_path / 'warp.json'
    plan = prepare_import(source, target)
    assert plan.duplicate_count == 1
    assert save_import(plan) is None
    assert prepare_import(source, target).added_count == 0


def test_mismatch_preserves(files):
    source, target = files
    before = target.read_bytes()
    put(source, data(uid='100000002'))
    with pytest.raises(WarpImportError, match='账号不一致'):
        prepare_import(source, target)
    assert target.read_bytes() == before


@pytest.mark.parametrize('field,value', [('lang', 'en-us'), ('region_time_zone', -5)])
def test_locale_mismatch(files, field, value):
    source, target = files
    other = data(); other['info'][field] = value
    put(source, other)
    with pytest.raises(WarpImportError, match='语言或时区'):
        prepare_import(source, target)


def test_single_uigf(tmp_path):
    sample = data()
    source = put(tmp_path / 'input.json', {'info': {'version': 'v4.1'}, 'hkrpg': [
        {'uid': sample['info']['uid'], 'timezone': 8, 'lang': 'zh-cn', 'list': sample['list']}]})
    assert prepare_import(source, tmp_path / 'warp.json').data['list'] == sample['list']


@pytest.mark.parametrize('accounts', [[], [{}, {}]])
def test_multiple_or_empty_accounts(accounts):
    with pytest.raises(WarpImportError, match='单账号'):
        normalize({'info': {}, 'hkrpg': accounts})


@pytest.mark.parametrize('mutation', [
    lambda d: d['info'].pop('uid'),
    lambda d: d['list'][0].pop('id'),
    lambda d: d['list'][0].update(id=True),
    lambda d: d['list'][0].update(uid='200000002'),
    lambda d: d['list'][0].update(gacha_type='999'),
    lambda d: d['list'][0].update(time='invalid'),
    lambda d: d['list'][0].pop('name'),
])
def test_invalid_records(mutation):
    sample = data(); mutation(sample)
    with pytest.raises(WarpImportError):
        normalize(sample)


def test_conflicting_id(files):
    source, target = files
    incoming = data(); incoming['list'][0]['name'] = '其他角色'
    put(source, incoming)
    with pytest.raises(WarpImportError, match='内容不一致'):
        prepare_import(source, target)


def test_changed_after_preview(files):
    source, target = files
    plan = prepare_import(source, target)
    put(target, data((4,)))
    before = target.read_bytes()
    with pytest.raises(WarpImportError, match='发生变化'):
        save_import(plan)
    assert target.read_bytes() == before


@pytest.mark.parametrize('operation', ['replace', 'fsync'])
def test_failed_write_keeps_original(files, operation):
    source, target = files
    plan = prepare_import(source, target)
    with patch('app.tools.warp_import.os.' + operation, side_effect=OSError('disk error')):
        with pytest.raises(OSError):
            save_import(plan)
    assert target.read_bytes() == plan.original
    assert not list(target.parent.glob('*.tmp'))


def test_bad_existing_file_never_overwritten(files):
    source, target = files
    target.write_bytes(b'{invalid')
    with pytest.raises(ValueError):
        prepare_import(source, target)
    assert target.read_bytes() == b'{invalid'


def test_mutation_before_replace(files):
    source, target = files
    plan = prepare_import(source, target)
    import app.tools.warp_import as module
    check = module._unchanged
    calls = []
    def concurrent(plan):
        calls.append(1)
        if len(calls) == 2:
            put(target, data((99,)))
        check(plan)
    with patch.object(module, '_unchanged', concurrent), pytest.raises(WarpImportError):
        save_import(plan)
    assert json.loads(target.read_bytes())['list'][0]['id'] == '99'


def test_explicit_replace_keeps_exact_backup(files):
    source, target = files
    before = target.read_bytes()
    plan = prepare_import(source, target, mode='replace')
    assert plan.mode == 'replace' and plan.removed_count == 1
    backup = save_import(plan)
    assert backup.read_bytes() == before
    assert [r['id'] for r in json.loads(target.read_bytes())['list']] == ['2', '3']


def test_replace_allows_conflict_and_locale_change(files):
    source, target = files
    incoming = data(); incoming['list'][0]['name'] = 'March 7th'
    incoming['info']['lang'] = 'en-us'
    incoming['info']['region_time_zone'] = -5
    put(source, incoming)
    plan = prepare_import(source, target, mode='replace')
    save_import(plan)
    assert json.loads(target.read_bytes()) == incoming


def test_explicit_replace_can_change_single_account(files):
    source, target = files
    before = target.read_bytes()
    put(source, data(uid='100000002'))
    plan = prepare_import(source, target, mode='replace')
    assert plan.existing_uid == '100000001'
    backup = save_import(plan)
    assert backup.read_bytes() == before
    assert json.loads(target.read_bytes())['info']['uid'] == '100000002'


def test_replace_write_failure_preserves_original(files):
    source, target = files
    plan = prepare_import(source, target, mode='replace')
    with patch('app.tools.warp_import.os.replace', side_effect=OSError('locked')):
        with pytest.raises(OSError):
            save_import(plan)
    assert target.read_bytes() == plan.original
    assert next(target.parent.glob('*.bak')).read_bytes() == plan.original


def test_unknown_mode(files):
    source, target = files
    with pytest.raises(ValueError, match='Unknown import mode'):
        prepare_import(source, target, mode='unknown')


def test_replace_unreadable_file_backups_raw_bytes(files):
    source, target = files
    target.write_bytes(b'{broken')
    plan = prepare_import(source, target, mode='replace')
    assert plan.existing_unreadable
    backup = save_import(plan)
    assert backup.read_bytes() == b'{broken'
    assert len(json.loads(target.read_bytes())['list']) == 2
