# coding:utf-8
"""
로컬라이제이션 모듈
한국어/중국어 UI 언어 지원
"""
import json
import os

_current_lang = "zh_CN"
_translations = {}
_locale_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "locales")


def load_language(lang_code: str = None):
    """
    언어 파일 로드
    :param lang_code: 언어 코드 (zh_CN, ko_KR)
    """
    global _current_lang, _translations
    
    if lang_code is None:
        lang_code = "zh_CN"
    
    locale_path = os.path.join(_locale_dir, f"{lang_code}.json")
    
    if os.path.exists(locale_path):
        try:
            with open(locale_path, 'r', encoding='utf-8') as f:
                _translations = json.load(f)
            _current_lang = lang_code
        except Exception as e:
            print(f"언어 파일 로드 실패: {e}")
            _translations = {}
            _current_lang = "zh_CN"
    else:
        _translations = {}
        _current_lang = "zh_CN"


def tr(text: str) -> str:
    """
    번역 함수
    키가 없으면 원본 텍스트 반환 (중국어 원본 유지)
    :param text: 번역할 텍스트 (중국어 원본)
    :return: 번역된 텍스트
    """
    if not text:
        return text
    return _translations.get(text, text)


def get_current_language() -> str:
    """현재 언어 코드 반환"""
    return _current_lang


def get_available_languages() -> dict:
    """사용 가능한 언어 목록 반환"""
    return {
        "简体中文": "zh_CN",
        "한국어": "ko_KR"
    }
