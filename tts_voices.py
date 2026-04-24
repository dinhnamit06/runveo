# -*- coding: utf-8 -*-
from __future__ import annotations

from voice_profiles import get_base_language, normalize_locale


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


def is_edge_tts_voice_key(key: str | None) -> bool:
    text = str(key or "").strip()
    return any(item["key"] == text for item in EDGE_TTS_VOICES) or text.endswith("Neural")


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


def get_edge_tts_choices(target_locale: str | None = None) -> list[tuple[str, str]]:
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

    exact = [item for item in EDGE_TTS_VOICES if normalize_locale(item.get("locale")) == normalized_target]
    if exact:
        voices = sorted(exact, key=rank)
        return [(item["key"], item["label"]) for item in voices]

    same_base = [
        item for item in EDGE_TTS_VOICES
        if target_base and get_base_language(item.get("locale")) == target_base
    ]
    voices = sorted(same_base or EDGE_TTS_VOICES, key=rank)
    return [(item["key"], item["label"]) for item in voices]
