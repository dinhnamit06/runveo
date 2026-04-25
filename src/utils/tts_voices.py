# -*- coding: utf-8 -*-
from __future__ import annotations

from src.utils.voice_profiles import get_base_language, normalize_locale


EDGE_TTS_DEFAULT = "vi-VN-HoaiMyNeural"


EDGE_TTS_VOICES: list[dict[str, str]] = [
    {"key": "vi-VN-HoaiMyNeural", "label": "Hoài My (Nữ)", "locale": "vi-VN", "gender": "female"},
    {"key": "vi-VN-NamMinhNeural", "label": "Nam Minh (Nam)", "locale": "vi-VN", "gender": "male"},
    {"key": "en-US-JennyNeural", "label": "Jenny (Nữ)", "locale": "en-US", "gender": "female"},
    {"key": "en-US-GuyNeural", "label": "Guy (Nam)", "locale": "en-US", "gender": "male"},
    {"key": "en-GB-SoniaNeural", "label": "Sonia (Nữ)", "locale": "en-GB", "gender": "female"},
    {"key": "en-GB-RyanNeural", "label": "Ryan (Nam)", "locale": "en-GB", "gender": "male"},
    {"key": "zh-CN-XiaoxiaoNeural", "label": "Xiaoxiao (Nữ)", "locale": "zh-CN", "gender": "female"},
    {"key": "zh-CN-YunxiNeural", "label": "Yunxi (Nam)", "locale": "zh-CN", "gender": "male"},
    {"key": "ja-JP-NanamiNeural", "label": "Nanami (Nữ)", "locale": "ja-JP", "gender": "female"},
    {"key": "ja-JP-KeitaNeural", "label": "Keita (Nam)", "locale": "ja-JP", "gender": "male"},
    {"key": "ko-KR-SunHiNeural", "label": "SunHi (Nữ)", "locale": "ko-KR", "gender": "female"},
    {"key": "ko-KR-InJoonNeural", "label": "InJoon (Nam)", "locale": "ko-KR", "gender": "male"},
]


TIKTOK_TTS_DEFAULT = "tiktok_vn_female_1"


TIKTOK_TTS_VOICES: list[dict[str, str]] = [
    {"key": "tiktok_vn_female_1", "label": "Nữ tự nhiên", "locale": "vi-VN", "gender": "female"},
    {"key": "tiktok_vn_male_1", "label": "Nam tự nhiên", "locale": "vi-VN", "gender": "male"},
    {"key": "tiktok_en_us_female", "label": "Nữ phổ thông", "locale": "en-US", "gender": "female"},
    {"key": "tiktok_en_us_jessie", "label": "Jessie", "locale": "en-US", "gender": "female"},
    {"key": "tiktok_en_us_male_1", "label": "Nam trẻ", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_us_male_2", "label": "Nam trầm", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_uk_male", "label": "Nam trang trọng", "locale": "en-GB", "gender": "male"},
    {"key": "tiktok_en_us_ghostface", "label": "Ghostface", "locale": "en-US", "gender": "male"},
    {"key": "tiktok_en_us_stormtrooper", "label": "Stormtrooper", "locale": "en-US", "gender": "male"},
]


def is_edge_tts_voice_key(key: str | None) -> bool:
    text = str(key or "").strip()
    return any(item["key"] == text for item in EDGE_TTS_VOICES) or text.endswith("Neural")


def is_tiktok_tts_voice_key(key: str | None) -> bool:
    text = str(key or "").strip()
    return any(item["key"] == text for item in TIKTOK_TTS_VOICES)


def get_edge_tts_voice_metadata(key: str | None) -> dict[str, str]:
    text = str(key or "").strip()
    for item in EDGE_TTS_VOICES:
        if item["key"] == text:
            return dict(item)
    if text.endswith("Neural"):
        locale = "-".join(text.split("-")[:2]) if "-" in text else ""
        return {
            "key": text,
            "label": text,
            "locale": normalize_locale(locale) or "vi-VN",
            "gender": "female" if any(name in text.lower() for name in ("female", "my", "jenny", "sonia", "xiaoxiao", "nanami", "sunhi")) else "male",
        }
    return get_edge_tts_voice_metadata(EDGE_TTS_DEFAULT)


def get_edge_tts_voice_label(key: str | None) -> str:
    return str(get_edge_tts_voice_metadata(key).get("label") or key or EDGE_TTS_DEFAULT)


def get_tiktok_tts_voice_metadata(key: str | None) -> dict[str, str]:
    text = str(key or "").strip()
    for item in TIKTOK_TTS_VOICES:
        if item["key"] == text:
            return dict(item)
    return get_tiktok_tts_voice_metadata(TIKTOK_TTS_DEFAULT)


def _choices_for_locale(voices: list[dict[str, str]], target_locale: str | None) -> list[tuple[str, str]]:
    normalized_target = normalize_locale(target_locale) or "vi-VN"
    target_base = get_base_language(normalized_target)

    def rank(item: dict[str, str]) -> tuple[int, str]:
        locale = normalize_locale(item.get("locale"))
        base = get_base_language(locale)
        if locale == normalized_target:
            return (0, item["key"])
        if base == target_base:
            return (1, item["key"])
        if locale == "vi-VN":
            return (2, item["key"])
        return (3, item["key"])

    exact = [item for item in voices if normalize_locale(item.get("locale")) == normalized_target]
    if exact:
        selected = sorted(exact, key=rank)
        return [(item["key"], item["label"]) for item in selected]

    same_base = [
        item for item in voices
        if target_base and get_base_language(item.get("locale")) == target_base
    ]
    selected = sorted(same_base or voices, key=rank)
    return [(item["key"], item["label"]) for item in selected]


def get_edge_tts_choices(target_locale: str | None = None) -> list[tuple[str, str]]:
    return _choices_for_locale(EDGE_TTS_VOICES, target_locale)


def get_tiktok_tts_choices(target_locale: str | None = None) -> list[tuple[str, str]]:
    normalized_target = normalize_locale(target_locale) or "vi-VN"
    target_base = get_base_language(normalized_target)
    exact = [
        item for item in TIKTOK_TTS_VOICES
        if normalize_locale(item.get("locale")) == normalized_target
    ]
    same_base = [
        item for item in TIKTOK_TTS_VOICES
        if target_base and get_base_language(item.get("locale")) == target_base
    ]
    voices = exact or same_base
    return [(item["key"], item["label"]) for item in voices]
