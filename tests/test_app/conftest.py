import pytest

from module import localization


@pytest.fixture(scope="package", autouse=True)
def _use_compiled_locales(compiled_locales):
    language = localization.get_current_language()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(localization, "_locale_dir", compiled_locales)
        localization.load_language(language)
        yield
    localization.load_language(language)
