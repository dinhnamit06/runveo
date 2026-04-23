# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable


LANGUAGE_FALLBACKS: dict[str, list[str]] = {
    "en-AU": ["en-GB", "en-US", "en"],
    "en-CA": ["en-US", "en-GB", "en"],
    "en-IN": ["en-GB", "en-US", "en"],
    "vi-VN": ["en-US", "en"],
    "es-MX": ["es-ES", "es"],
    "es-ES": ["es-MX", "es"],
}


VOICE_JSON: dict[str, dict] = {
    "None_NoVoice": {
        "label": "Không có giọng đọc",
        "locale": "*",
        "language": "*",
        "gender": "neutral",
        "style": "none",
        "priority": 0,
        "enabled": True,
        "aliases": ["*", "none"],
        "fallback_locales": [],
        "voice_profile": "",
    },
    "Nam_Kechuyen": {
        "label": "Nam Việt - Kể chuyện",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "epic",
        "priority": 100,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "A high-fidelity studio recording of a middle-aged Vietnamese male narrator. "
            "Deep resonant timbre, cinematic authority, deliberate pacing, crisp articulation."
        ),
    },
    "Nu_Kechuyen": {
        "label": "Nữ Việt - Kể chuyện",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "warm_storytelling",
        "priority": 95,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Professional Vietnamese female storyteller with warm emotional delivery, soft melodic tone, "
            "clear diction, and elegant cinematic phrasing."
        ),
    },
    "Nam_Tre": {
        "label": "Nam Việt - Trẻ trung",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "energetic",
        "priority": 90,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Young Vietnamese adult male voice with energetic delivery, modern rhythm, bright presence, "
            "and friendly upbeat articulation."
        ),
    },
    "Nu_Tre": {
        "label": "Nữ Việt - Trẻ trung",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "sweet",
        "priority": 90,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Young Vietnamese female voice with bright sweetness, cheerful expression, clean pronunciation, "
            "and lively social-media-friendly pacing."
        ),
    },
    "Nam_Gia": {
        "label": "Nam Việt - Trung niên",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "wise",
        "priority": 80,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Elder Vietnamese male voice with wise calm delivery, deep warmth, slight age texture, "
            "measured pacing, and trustworthy presence."
        ),
    },
    "Nu_Gia": {
        "label": "Nữ Việt - Trung niên",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "nurturing",
        "priority": 80,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Elder Vietnamese female voice with nurturing warmth, stable cadence, comforting tone, "
            "and gentle maternal reassurance."
        ),
    },
    "Nam_Phim": {
        "label": "Nam Việt - Giọng phim",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "cinematic_trailer",
        "priority": 88,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Vietnamese cinematic male trailer voice with gritty low-end texture, intense authority, "
            "dramatic emphasis, and high-impact punch."
        ),
    },
    "Nu_Phim": {
        "label": "Nữ Việt - Giọng phim",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "cinematic_suspense",
        "priority": 87,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Vietnamese female cinematic suspense voice with breathy tension, sharp control, mysterious energy, "
            "and dramatic contrast."
        ),
    },
    "Nam_Review": {
        "label": "Nam Việt - Review",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "review_fast",
        "priority": 75,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Fast Vietnamese male reviewer voice with concise delivery, energetic persuasion, "
            "clear structure, and charismatic information density."
        ),
    },
    "Nu_Review": {
        "label": "Nữ Việt - Review",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "review_fast",
        "priority": 75,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Fast Vietnamese female reviewer voice with articulate professional pacing, bright authority, "
            "and persuasive but friendly control."
        ),
    },
    "Nam_Hai": {
        "label": "Nam Việt - Hài hước",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "comedic",
        "priority": 70,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Comedic Vietnamese male voice with playful timing, expressive pitch movement, animated phrasing, "
            "and lively humorous exaggeration."
        ),
    },
    "Nam_Tram_Duc": {
        "label": "Nam Việt - Trầm đục",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "deep_bass",
        "priority": 92,
        "enabled": True,
        "aliases": ["vi", "vi_VN"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "Extremely deep Vietnamese male bass with gravel texture, weighted authority, low register presence, "
            "and commanding cinematic gravity."
        ),
    },
    "US_Male_Epic": {
        "label": "Nam Mỹ - Hùng tráng",
        "locale": "en-US",
        "language": "en",
        "gender": "male",
        "style": "cinematic",
        "priority": 100,
        "enabled": True,
        "aliases": ["en-US", "en_US", "en"],
        "fallback_locales": ["en-GB"],
        "voice_profile": (
            "Professional American male narrator with deep cinematic tone, polished studio fidelity, "
            "strong gravitas, and trailer-grade dramatic control."
        ),
    },
    "US_Female_Warm": {
        "label": "Nữ Mỹ - Ấm áp",
        "locale": "en-US",
        "language": "en",
        "gender": "female",
        "style": "warm_storytelling",
        "priority": 95,
        "enabled": True,
        "aliases": ["en-US", "en_US", "en"],
        "fallback_locales": ["en-GB"],
        "voice_profile": (
            "Professional American female storyteller with warm clarity, emotional nuance, intimate presence, "
            "and elegant commercial-grade delivery."
        ),
    },
    "EN_GB_Narrator": {
        "label": "Người dẫn truyện Anh",
        "locale": "en-GB",
        "language": "en",
        "gender": "neutral",
        "style": "narrator",
        "priority": 92,
        "enabled": True,
        "aliases": ["en-GB", "en_GB", "en"],
        "fallback_locales": ["en-US"],
        "voice_profile": (
            "British narrator voice with refined control, clean diction, measured authority, "
            "and polished documentary storytelling balance."
        ),
    },
}


VOICE_OPTIONS = list(VOICE_JSON.keys())


def normalize_locale(value: str | None) -> str:
    raw = str(value or "").strip().replace("_", "-")
    if not raw:
        return ""
    if raw == "*":
        return "*"
    parts = [part for part in raw.split("-") if part]
    if not parts:
        return ""
    base = parts[0].lower()
    if len(parts) == 1:
        return base
    normalized = [base]
    for idx, part in enumerate(parts[1:], start=1):
        if idx == 1 and len(part) <= 3:
            normalized.append(part.upper())
        else:
            normalized.append(part.title())
    return "-".join(normalized)


def get_base_language(value: str | None) -> str:
    normalized = normalize_locale(value)
    if not normalized or normalized == "*":
        return ""
    return normalized.split("-", 1)[0].lower()


def get_voice_metadata(key: str | None) -> dict:
    return dict(VOICE_JSON.get(str(key or "").strip(), VOICE_JSON["None_NoVoice"]))


def get_voice_label(key: str | None) -> str:
    meta = get_voice_metadata(key)
    return str(meta.get("label") or "Không có giọng đọc")


def get_voice_profile_text(key: str | None) -> str:
    meta = get_voice_metadata(key)
    return str(meta.get("voice_profile") or "").strip()


def get_voice_locale(key: str | None) -> str:
    meta = get_voice_metadata(key)
    return normalize_locale(meta.get("locale"))


def get_voice_language(key: str | None) -> str:
    meta = get_voice_metadata(key)
    return get_base_language(meta.get("language") or meta.get("locale"))


def _voice_enabled(meta: dict) -> bool:
    return bool(meta.get("enabled", True))


def _normalized_aliases(meta: dict) -> set[str]:
    aliases: set[str] = set()
    locale = normalize_locale(meta.get("locale"))
    language = get_base_language(meta.get("language") or locale)
    if locale:
        aliases.add(locale)
    if language:
        aliases.add(language)
    raw_aliases = meta.get("aliases") or []
    if isinstance(raw_aliases, Iterable) and not isinstance(raw_aliases, (str, bytes)):
        for alias in raw_aliases:
            normalized = normalize_locale(alias)
            if normalized:
                aliases.add(normalized)
                base = get_base_language(normalized)
                if base:
                    aliases.add(base)
    return aliases


def _fallback_candidates(target_locale: str) -> list[str]:
    if not target_locale or target_locale == "*":
        return []
    base = get_base_language(target_locale)
    candidates: list[str] = []
    for item in LANGUAGE_FALLBACKS.get(target_locale, []):
        normalized = normalize_locale(item)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    if base and base not in candidates:
        candidates.append(base)
    return candidates


def get_enabled_voice_keys() -> list[str]:
    keys = [key for key in VOICE_OPTIONS if _voice_enabled(get_voice_metadata(key))]
    return sorted(keys, key=lambda key: (-int(get_voice_metadata(key).get("priority", 0)), key))


def get_best_voice(target_language: str | None, preferred_key: str | None = None) -> str:
    normalized_target = normalize_locale(target_language)
    target_base = get_base_language(normalized_target)

    preferred = str(preferred_key or "").strip()
    if preferred in VOICE_JSON and _voice_enabled(get_voice_metadata(preferred)):
        meta = get_voice_metadata(preferred)
        aliases = _normalized_aliases(meta)
        if normalized_target in aliases or target_base in aliases or normalized_target in {"", "*"}:
            return preferred

    enabled_keys = get_enabled_voice_keys()
    if not enabled_keys:
        return "None_NoVoice"

    def _sorted_keys(keys: list[str]) -> list[str]:
        return sorted(keys, key=lambda key: (-int(get_voice_metadata(key).get("priority", 0)), key))

    exact = [key for key in enabled_keys if normalize_locale(get_voice_metadata(key).get("locale")) == normalized_target]
    if exact:
        return _sorted_keys(exact)[0]

    alias_match = [key for key in enabled_keys if normalized_target and normalized_target in _normalized_aliases(get_voice_metadata(key))]
    if alias_match:
        return _sorted_keys(alias_match)[0]

    base_match = [key for key in enabled_keys if target_base and target_base in _normalized_aliases(get_voice_metadata(key))]
    if base_match:
        return _sorted_keys(base_match)[0]

    fallback_hits: list[str] = []
    for fallback_locale in _fallback_candidates(normalized_target):
        for key in enabled_keys:
            aliases = _normalized_aliases(get_voice_metadata(key))
            if fallback_locale in aliases:
                fallback_hits.append(key)
        if fallback_hits:
            return _sorted_keys(list(dict.fromkeys(fallback_hits)))[0]

    if "None_NoVoice" in VOICE_JSON and _voice_enabled(VOICE_JSON["None_NoVoice"]):
        return "None_NoVoice"
    return _sorted_keys(enabled_keys)[0]


def get_voice_choices(target_language: str | None = None, include_none: bool = True) -> list[tuple[str, str]]:
    normalized_target = normalize_locale(target_language)
    target_base = get_base_language(normalized_target)
    ranked: list[tuple[int, int, str]] = []

    for key in VOICE_OPTIONS:
        meta = get_voice_metadata(key)
        if not _voice_enabled(meta):
            continue
        if key == "None_NoVoice":
            if include_none:
                ranked.append((99, 0, key))
            continue
        aliases = _normalized_aliases(meta)
        score = 4
        if normalized_target and normalize_locale(meta.get("locale")) == normalized_target:
            score = 0
        elif normalized_target and normalized_target in aliases:
            score = 1
        elif target_base and target_base in aliases:
            score = 2
        elif normalized_target and any(fallback in aliases for fallback in _fallback_candidates(normalized_target)):
            score = 3
        ranked.append((score, -int(meta.get("priority", 0)), key))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    choices = [(key, get_voice_label(key)) for _, _, key in ranked]
    if include_none and not any(key == "None_NoVoice" for key, _ in choices):
        choices.append(("None_NoVoice", get_voice_label("None_NoVoice")))
    return choices
