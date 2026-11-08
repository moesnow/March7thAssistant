import base64
import json
from unittest.mock import Mock

import pytest

from module.update import changelog
from utils.version import Version


DOCUMENT = """# 更新日志
## v2026.10.16
- 文档中的最新说明
## v2026.9.30
- 九月更新
## v2026.10.3
- 十月更新
## v2026.9.25
- 已安装的版本
## v2026.10.17
- 未来版本
"""


def test_range_sort_and_release_note_precedence():
    result = changelog.collect_update_notes(DOCUMENT, 'v2026.9.25', 'v2026.10.16', '- 发布后的补充')
    assert [s.version for s in result.sections] == ['v2026.10.16', 'v2026.10.3', 'v2026.9.30']
    assert result.sections[0].markdown == '- 发布后的补充'
    assert not result.partial


def test_unlisted_current_version_and_empty_release_body():
    result = changelog.collect_update_notes(DOCUMENT, 'v2026.9.28', 'v2026.10.16', '')
    assert len(result.sections) == 3
    assert result.sections[0].markdown == '- 文档中的最新说明'


def test_parser_skips_fences_hidden_headings_and_invalid_versions():
    document = """## v2.0
- 保留
```
## v9.0
```
<!-- m7a:hide -->
## v8.0
<!-- /m7a:hide -->
## v2.0
- 重复版本不覆盖
## v1.5-garbage
- 不收录
## 其他内容
- 不属于 v2.0
## v1.0 ##
- 历史
"""
    parsed = changelog.parse_changelog(document)
    assert set(parsed) == {Version('2.0'), Version('1.0')}
    assert '保留' in parsed[Version('2.0')].markdown
    assert '不属于' not in parsed[Version('2.0')].markdown
    assert '不覆盖' not in parsed[Version('2.0')].markdown


@pytest.mark.parametrize('current,target', [('', 'v2.0'), ('broken', 'v2.0'), ('v2.0', 'v2.0'), ('v3.0', 'v2.0')])
def test_invalid_range_does_not_invent_history(current, target):
    with pytest.raises(ValueError):
        changelog.collect_update_notes('## v2.0\n- 新版', current, target, '- 新版')


def test_prerelease_filter_and_missing_beta_section():
    document = '## v2.0\n- 正式版\n## v2.0-beta\n- 公测\n## v1.0\n- 旧版'
    stable = changelog.collect_update_notes(document, 'v1.0', 'v2.0', '')
    assert len(stable.sections) == 1
    beta = changelog.collect_update_notes(document, 'v1.0', 'v2.0', '', True)
    assert [s.version for s in beta.sections] == ['v2.0', 'v2.0-beta']
    missing = changelog.collect_update_notes(document, 'v1.0', 'v3.0-beta', '- 新公测', True)
    assert missing.sections[0].version == 'v3.0-beta'
    assert missing.partial


def test_partial_history_and_missing_target():
    assert changelog.collect_update_notes('## v2.0\n- 新版', 'v1.0', 'v2.0', '').partial
    with pytest.raises(ValueError, match='目标版本'):
        changelog.collect_update_notes('## v1.0\n- 旧版', 'v1.0', 'v2.0', '- 新版')


@pytest.fixture
def network(monkeypatch):
    changelog._CACHE.clear()
    monkeypatch.setattr(changelog, 'get_update_download_requests_proxies', lambda: {'https': 'http://proxy:1234'})
    get = Mock()
    monkeypatch.setattr(changelog.requests, 'get', get)
    yield get
    changelog._CACHE.clear()


NETWORK_DOCUMENT = DOCUMENT.split('## v2026.10.17')[0]


def response(document=NETWORK_DOCUMENT, **overrides):
    data = {'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(document.encode()).decode()}
    data.update(overrides)
    obj = Mock()
    obj.__enter__ = Mock(return_value=obj)
    obj.__exit__ = Mock(return_value=False)
    obj.status_code = 200
    obj.iter_content.return_value = [json.dumps(data).encode()]
    return obj


def test_fetch_pinned_ref_preferred_mirror_proxy_and_cache(network):
    network.return_value = response()
    mirror = changelog.GITHUB_API_BASES[1]
    assert changelog.fetch_changelog('v2026.10.16', preferred_base=mirror) == NETWORK_DOCUMENT
    args, kwargs = network.call_args
    assert args[0] == mirror + '/contents/assets/docs/Changelog.md'
    assert kwargs['params'] == {'ref': 'v2026.10.16'}
    assert kwargs['proxies'] == {'https': 'http://proxy:1234'}
    assert kwargs['headers']['Accept'] == 'application/vnd.github+json'
    assert changelog.fetch_changelog('v2026.10.16') == NETWORK_DOCUMENT
    assert network.call_count == 1


def test_bad_response_falls_back_without_caching_failure(network):
    network.side_effect = [response(encoding='none'), response()]
    assert changelog.fetch_changelog('v2026.10.16') == NETWORK_DOCUMENT
    assert network.call_count == 2
    changelog._CACHE.clear()
    network.side_effect = OSError('offline')
    with pytest.raises(RuntimeError):
        changelog.fetch_changelog('v2026.10.16')
    assert not changelog._CACHE


def test_total_budget_stops_next_mirror(network, monkeypatch):
    clock = [0]
    monkeypatch.setattr(changelog.time, 'monotonic', lambda: clock[0])
    def timed_out(*args, **kwargs):
        clock[0] = 6
        raise TimeoutError()
    network.side_effect = timed_out
    with pytest.raises(RuntimeError):
        changelog.fetch_changelog('v2026.10.16', timeout=5)
    assert network.call_count == 1


def test_stream_size_and_cancellation_are_bounded(network, monkeypatch):
    oversized = response()
    oversized.iter_content.return_value = [b'x' * (changelog._MAX_BYTES + 1)]
    network.return_value = oversized
    with pytest.raises(RuntimeError):
        changelog.fetch_changelog('v2026.10.16')
    assert not changelog._CACHE
    network.reset_mock()
    with pytest.raises(changelog.ChangelogCancelled):
        changelog.fetch_changelog('v2026.10.16', cancelled=lambda: True)
    network.assert_not_called()


def test_strict_version_is_opt_in():
    assert Version('v1.0-garbage') == Version('v1.0')
    with pytest.raises(ValueError):
        Version('v1.0-garbage', strict=True)
    assert Version('v2.0-rc1').is_prerelease
    assert Version('v2.0.dev1').is_prerelease
    assert not Version('v2.0-1').is_prerelease


def test_redirect_keeps_tag_and_uses_shared_budget(network):
    redirected = response()
    redirected.status_code = 302
    url = changelog.GITHUB_API_BASES[0] + '/contents/assets/docs/Changelog.md?ref=v2026.10.16'
    redirected.headers = {'Location': url}
    network.side_effect = [redirected, response()]
    assert changelog.fetch_changelog('v2026.10.16') == NETWORK_DOCUMENT
    assert network.call_args.args == (url,)
    assert network.call_args.kwargs['params'] is None
    assert network.call_args.kwargs['allow_redirects'] is False


def test_redirect_without_ref_and_wrong_tag_document_are_rejected(network):
    redirected = response()
    redirected.status_code = 302
    redirected.headers = {'Location': changelog.GITHUB_API_BASES[0] + '/contents/assets/docs/Changelog.md'}
    network.return_value = redirected
    with pytest.raises(RuntimeError):
        changelog.fetch_changelog('v2026.10.16')
    assert not changelog._CACHE
    network.return_value = response(DOCUMENT)
    with pytest.raises(RuntimeError):
        changelog.fetch_changelog('v2026.10.16')
    assert not changelog._CACHE
