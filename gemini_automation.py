# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from playwright.async_api import async_playwright

from chrome import CDP_HOST, CDP_PORT, pick_cdp_port_for_new_session, wait_for_cdp
from chrome_process_manager import ChromeProcessManager
from settings_manager import SettingsManager
from voice_profiles import normalize_locale


GEMINI_URL = "https://gemini.google.com/app"
GEMINI_HIDDEN_FILE_UPLOAD_TRIGGER_SELECTOR = (
    'button[data-test-id="hidden-local-file-upload-button"].hidden-local-file-upload-button[xapfileselectortrigger]'
)
GEMINI_UPLOAD_MENU_BUTTON_SELECTORS = [
    'button.upload-card-button[aria-label="Open upload file menu"][aria-controls="upload-file-menu"]',
    'button.upload-card-button[aria-controls="upload-file-menu"]',
    'button:has(mat-icon[fonticon="add_2"])',
    'button[aria-label*="Upload image"]',
    'button[aria-label*="Tải hình ảnh"]',
    'button[aria-label*="Upload files"]',
    'button[aria-label*="Tải tệp"]',
    'button[aria-label*="Upload"]',
    'button:has(mat-icon[fonticon="add_circle"])',
]
GEMINI_UPLOAD_MENU_ITEM_TEXTS = [
    "Upload files",
    "Tải tệp lên",
]
GEMINI_PROMPT_EDITOR_SELECTORS = [
    'div.ql-editor.textarea.new-input-ui[contenteditable="true"][role="textbox"][aria-label="Enter a prompt for Gemini"]',
    'div.ql-editor.textarea.new-input-ui[contenteditable="true"][role="textbox"]',
    'div.ql-editor.textarea.new-input-ui[contenteditable="true"][data-placeholder="Ask Gemini"]',
    'div.ql-editor[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"][role="textbox"][aria-multiline="true"]',
]
GEMINI_SEND_BUTTON_SELECTORS = [
    'button.send-button.submit[aria-label="Send message"]',
    'button.send-button.submit[aria-label="Gửi tin nhắn"]',
    "button.send-button.submit",
]
GEMINI_READY_SELECTORS = [
    *GEMINI_UPLOAD_MENU_BUTTON_SELECTORS,
    GEMINI_HIDDEN_FILE_UPLOAD_TRIGGER_SELECTOR,
    *GEMINI_PROMPT_EDITOR_SELECTORS,
    *GEMINI_SEND_BUTTON_SELECTORS,
]


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_copy_strength(value: Any) -> int:
    try:
        strength = int(value)
    except Exception:
        strength = 100
    return max(50, min(100, strength))


def _normalize_user_edit_instruction(value: Any, max_chars: int = 1600) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def _copy_strength_prompt_block(copy_strength: int) -> str:
    strength = _normalize_copy_strength(copy_strength)
    if strength <= 60:
        strategy = (
            "50% inspired adaptation: copy only the core idea, core visual style, and emotional arc. "
            "Do not recreate exact dialogue, exact characters, exact outfits, exact props, exact setting, or shot-by-shot staging. "
            "Create a fresh short-video version with a clear opening, body/development, and ending/resolution."
        )
    elif strength <= 75:
        strategy = (
            "medium adaptation: keep the main concept, story beats, pacing, and visual style, but change specific visual details, "
            "character designs, locations, props, and some actions enough to feel original."
        )
    elif strength < 100:
        strategy = (
            "close adaptation: preserve most scene beats, camera language, pacing, and style, with light variation in wording and secondary details."
        )
    else:
        strategy = "100% faithful recreation: preserve source structure, scene order, actions, camera language, dialogue meaning, and style as closely as possible."

    return (
        f"Copy strength: {strength}%.\n"
        f"Strategy for this task: {strategy}\n"
        "Narrative requirement: every output must work as a complete short video with opening, body/development, and ending/resolution. "
        "Use narrative_role values such as opening, body, and ending for scenes.\n"
    )


def _normalize_scene_ids(raw_ids: Any, default_character_ids: list[str]) -> list[str]:
    out: list[str] = []
    if isinstance(raw_ids, list):
        for item in raw_ids:
            text = _normalize_text(item)
            if text and text not in out:
                out.append(text)
    if out:
        return out
    return list(default_character_ids)


def _normalize_copy_video_payload(
    data: dict,
    target_language: str,
    copy_strength: int | None = None,
    user_edit_instruction: str = "",
) -> dict:
    normalized_target = normalize_locale(target_language) or "en-US"
    normalized_strength = _normalize_copy_strength(
        copy_strength
        if copy_strength is not None
        else data.get("copy_strength_percent") or data.get("copy_strength") or data.get("copy_level_percent") or 100
    )
    user_instruction = _normalize_user_edit_instruction(
        user_edit_instruction
        or data.get("user_edit_instruction")
        or data.get("user_edit_instruction_en")
        or data.get("custom_instruction")
        or data.get("custom_instruction_en")
    )
    detected_source = (
        normalize_locale(data.get("detected_source_language"))
        or normalize_locale(data.get("source_language"))
        or normalize_locale(data.get("source_locale"))
        or "auto"
    )

    characters_raw = data.get("characters")
    legacy_identity = _normalize_text(data.get("identity_lock") or data.get("identity_lock_en"))
    characters: list[dict[str, Any]] = []

    if isinstance(characters_raw, list):
        for idx, item in enumerate(characters_raw, start=1):
            if not isinstance(item, dict):
                continue
            character_id = _normalize_text(item.get("character_id") or f"char_{idx:02d}")
            identity_lock_en = _normalize_text(item.get("identity_lock_en") or item.get("identity_lock"))
            if not identity_lock_en:
                continue
            characters.append(
                {
                    "character_id": character_id,
                    "identity_lock_en": identity_lock_en,
                }
            )

    if not characters and legacy_identity:
        characters.append(
            {
                "character_id": "char_01",
                "identity_lock_en": legacy_identity,
            }
        )

    default_character_ids = [item["character_id"] for item in characters]

    scenes_raw = data.get("scenes")
    scenes: list[dict[str, Any]] = []
    if isinstance(scenes_raw, list):
        for idx, item in enumerate(scenes_raw, start=1):
            if not isinstance(item, dict):
                continue
            scene_id = _normalize_text(item.get("scene_id") or f"scene_{idx:02d}")
            dialogue_original = _normalize_text(item.get("dialogue_original") or item.get("original_dialogue") or item.get("dialogue"))
            dialogue_target = _normalize_text(item.get("dialogue_target") or item.get("translated_dialogue") or dialogue_original)
            video_prompt_en = _normalize_text(item.get("video_prompt_en") or item.get("video_prompt"))
            if not video_prompt_en and not dialogue_target:
                continue
            scene_payload: dict[str, Any] = {
                "scene_id": scene_id,
                "character_ids": _normalize_scene_ids(item.get("character_ids"), default_character_ids),
                "dialogue_original": dialogue_original,
                "dialogue_target": dialogue_target,
                "video_prompt_en": video_prompt_en,
            }
            for text_key in (
                "shot_type",
                "camera_angle",
                "framing",
                "lens_feel",
                "scene_action_en",
                "visual_summary_en",
                "environment_en",
                "mood_en",
                "motion_en",
                "style_block_en",
                "render_consistency_en",
                "motion_style_en",
                "narrative_role",
                "copy_strategy_en",
                "user_edit_instruction_en",
                "custom_instruction_en",
                "adaptation_instruction_en",
            ):
                text_value = _normalize_text(item.get(text_key))
                if text_value:
                    scene_payload[text_key] = text_value
            for numeric_key in ("start_sec", "end_sec"):
                raw_value = item.get(numeric_key)
                try:
                    scene_payload[numeric_key] = float(raw_value)
                except Exception:
                    pass
            scenes.append(scene_payload)

    if not scenes:
        legacy_dialogue = _normalize_text(
            data.get("dialogue_original") or data.get("original_dialogue") or data.get("dialogue") or data.get("vietnamese_script")
        )
        legacy_translated = _normalize_text(data.get("dialogue_target") or legacy_dialogue)
        legacy_prompt = _normalize_text(data.get("video_prompt_en") or data.get("video_prompt"))
        if legacy_dialogue or legacy_prompt:
            scenes.append(
                {
                    "scene_id": "scene_01",
                    "character_ids": list(default_character_ids),
                    "dialogue_original": legacy_dialogue,
                    "dialogue_target": legacy_translated,
                    "video_prompt_en": legacy_prompt,
                }
            )

    if not characters:
        referenced_ids: list[str] = []
        for scene in scenes:
            for character_id in scene.get("character_ids", []):
                text = _normalize_text(character_id)
                if text and text not in referenced_ids:
                    referenced_ids.append(text)
        for idx, character_id in enumerate(referenced_ids or ["char_01"], start=1):
            characters.append(
                {
                    "character_id": character_id,
                    "identity_lock_en": f"consistent recurring character {idx}",
                }
            )

    for scene in scenes:
        scene["character_ids"] = _normalize_scene_ids(scene.get("character_ids"), [item["character_id"] for item in characters])
    total_scenes = len(scenes)
    for idx, scene in enumerate(scenes):
        if not _normalize_text(scene.get("narrative_role")):
            if total_scenes <= 1:
                scene["narrative_role"] = "opening-body-ending"
            elif idx == 0:
                scene["narrative_role"] = "opening"
            elif idx == total_scenes - 1:
                scene["narrative_role"] = "ending"
            else:
                scene["narrative_role"] = "body"

    out = {
        "schema_version": "copy_video_pro_v5",
        "copy_strength_percent": normalized_strength,
        "detected_source_language": detected_source,
        "target_language": normalized_target,
        "characters": characters,
        "scenes": scenes,
    }
    if user_instruction:
        out["user_edit_instruction"] = user_instruction
        out["user_edit_instruction_en"] = _normalize_text(data.get("user_edit_instruction_en")) or user_instruction
    return out


def _normalize_character_design_payload(data: dict, source_characters: list[dict[str, Any]]) -> dict:
    source_map: dict[str, dict[str, Any]] = {}
    for item in list(source_characters or []):
        if not isinstance(item, dict):
            continue
        character_id = _normalize_text(item.get("character_id"))
        if character_id:
            source_map[character_id] = item

    raw_characters = data.get("characters") if isinstance(data.get("characters"), list) else []
    normalized_characters: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for idx, item in enumerate(raw_characters, start=1):
        if not isinstance(item, dict):
            continue
        character_id = _normalize_text(item.get("character_id") or f"char_{idx:02d}")
        if not character_id or character_id in used_ids:
            continue
        source_item = source_map.get(character_id, {})
        entry: dict[str, Any] = {
            "character_id": character_id,
            "display_name": _normalize_text(item.get("display_name") or source_item.get("display_name") or character_id),
            "role": _normalize_text(item.get("role") or source_item.get("role")),
            "identity_lock_en": _normalize_text(item.get("identity_lock_en") or source_item.get("identity_lock_en")),
            "face_design_en": _normalize_text(item.get("face_design_en")),
            "hair_design_en": _normalize_text(item.get("hair_design_en")),
            "body_design_en": _normalize_text(item.get("body_design_en")),
            "wardrobe_en": _normalize_text(item.get("wardrobe_en")),
            "color_palette_en": _normalize_text(item.get("color_palette_en")),
            "reference_sheet_prompt_en": _normalize_text(item.get("reference_sheet_prompt_en")),
        }
        turnaround_raw = item.get("turnaround_prompts_en") if isinstance(item.get("turnaround_prompts_en"), dict) else {}
        turnaround: dict[str, str] = {}
        for view in ("front", "left", "right", "back"):
            value = _normalize_text(turnaround_raw.get(view))
            if value:
                turnaround[view] = value
        if turnaround:
            entry["turnaround_prompts_en"] = turnaround
        normalized_characters.append({k: v for k, v in entry.items() if v not in ("", None, {})})
        used_ids.add(character_id)

    if not normalized_characters:
        for idx, source_item in enumerate(source_characters or [], start=1):
            if not isinstance(source_item, dict):
                continue
            character_id = _normalize_text(source_item.get("character_id") or f"char_{idx:02d}")
            if not character_id or character_id in used_ids:
                continue
            normalized_characters.append(
                {
                    "character_id": character_id,
                    "display_name": _normalize_text(source_item.get("display_name") or character_id),
                    "role": _normalize_text(source_item.get("role")),
                    "identity_lock_en": _normalize_text(source_item.get("identity_lock_en")),
                }
            )
            used_ids.add(character_id)

    return {
        "schema_version": "copy_video_character_design_v1",
        "characters": normalized_characters,
    }


def _merge_character_design_into_source(source_data: dict, character_design: dict) -> dict:
    merged = dict(source_data or {})
    source_characters = merged.get("characters") if isinstance(merged.get("characters"), list) else []
    design_characters = character_design.get("characters") if isinstance(character_design.get("characters"), list) else []

    design_map: dict[str, dict[str, Any]] = {}
    for item in design_characters:
        if not isinstance(item, dict):
            continue
        character_id = _normalize_text(item.get("character_id"))
        if character_id:
            design_map[character_id] = item

    merged_characters: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for idx, source_item in enumerate(source_characters, start=1):
        if not isinstance(source_item, dict):
            continue
        character_id = _normalize_text(source_item.get("character_id") or f"char_{idx:02d}")
        if not character_id:
            continue
        combined = dict(source_item)
        combined.update(design_map.get(character_id, {}))
        combined["character_id"] = character_id
        if not _normalize_text(combined.get("display_name")):
            combined["display_name"] = character_id
        merged_characters.append(combined)
        used_ids.add(character_id)

    for item in design_characters:
        if not isinstance(item, dict):
            continue
        character_id = _normalize_text(item.get("character_id"))
        if not character_id or character_id in used_ids:
            continue
        combined = dict(item)
        if not _normalize_text(combined.get("display_name")):
            combined["display_name"] = character_id
        merged_characters.append(combined)
        used_ids.add(character_id)

    merged["characters"] = merged_characters
    merged["character_design"] = character_design
    return merged


class GeminiAutomation:
    def __init__(
        self,
        profile_path: str,
        headless: bool = False,
        bootstrap_url: str = "",
        log_callback: Callable[[str], None] | None = None,
    ):
        self.profile_path = profile_path
        self.headless = headless
        self.bootstrap_url = str(bootstrap_url or "").strip()
        self.log_callback = log_callback
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.debug_port = int(CDP_PORT or 9222)
        self._owns_page = False
        self._connected_over_cdp = False

    def _log(self, message: str) -> None:
        try:
            if callable(self.log_callback):
                self.log_callback(str(message))
        except Exception:
            pass

    def _resolve_shared_browser_settings(self) -> tuple[str, str]:
        profile_path = str(self.profile_path or "").strip()
        bootstrap_url = str(self.bootstrap_url or "").strip()
        try:
            config = SettingsManager.load_config()
        except Exception:
            config = {}

        account = config.get("account1", {}) if isinstance(config, dict) else {}
        if not profile_path:
            profile_path = str(account.get("folder_user_data_get_token") or "").strip()
        if not bootstrap_url:
            bootstrap_url = str(account.get("URL_GEN_TOKEN") or "").strip()

        if not profile_path:
            profile_path = str(
                os.getenv("CHROME_USER_DATA_DIR", "")
                or os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default")
            ).strip()
        if not bootstrap_url:
            bootstrap_url = "https://labs.google/fx/vi/tools/flow"

        return profile_path, bootstrap_url

    def _is_cdp_available(self, port: int) -> bool:
        try:
            with urlopen(f"http://{CDP_HOST}:{int(port)}/json/version", timeout=1.5) as response:
                if getattr(response, "status", 200) != 200:
                    return False
                raw = response.read() or b"{}"
            data = json.loads(raw.decode("utf-8", errors="ignore") or "{}")
            return isinstance(data, dict) and bool(
                data.get("webSocketDebuggerUrl") or data.get("Browser") or data.get("User-Agent")
            )
        except Exception:
            return False

    def _find_running_cdp_port_for_user_data(self, user_data_dir: str) -> int | None:
        target = str(user_data_dir or "").strip()
        if os.name != "nt" or not target:
            return None
        try:
            target_norm = str(Path(target).resolve()).lower().replace("/", "\\")
        except Exception:
            target_norm = target.lower().replace("/", "\\")

        try:
            ps_script = (
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "Select-Object -ExpandProperty CommandLine"
            )
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_script,
                ],
                capture_output=True,
                check=False,
            )
            output = bytes(proc.stdout or b"").decode("utf-8", errors="ignore")
        except Exception:
            return None

        for line in output.splitlines():
            cmd = str(line or "").strip().lower().replace("/", "\\")
            if not cmd or "--remote-debugging-port=" not in cmd or "--user-data-dir=" not in cmd:
                continue
            if target_norm not in cmd:
                continue
            match = re.search(r"--remote-debugging-port=(\d+)", cmd)
            if not match:
                continue
            try:
                return int(match.group(1))
            except Exception:
                continue
        return None

    async def start(self):
        profile_path, bootstrap_url = self._resolve_shared_browser_settings()
        self.profile_path = profile_path
        self.bootstrap_url = bootstrap_url

        existing_port = self._find_running_cdp_port_for_user_data(profile_path)
        if isinstance(existing_port, int) and self._is_cdp_available(existing_port):
            self.debug_port = int(existing_port)
        else:
            preferred_start = int(os.getenv("GEMINI_CDP_START_PORT", "9340") or "9340")
            candidate_ports: list[int] = []
            for base in (preferred_start, int(CDP_PORT or 9222)):
                try:
                    picked = int(pick_cdp_port_for_new_session(CDP_HOST, base))
                except Exception:
                    picked = int(base)
                for delta in range(0, 12):
                    port = int(picked + delta)
                    if port not in candidate_ports:
                        candidate_ports.append(port)

            launch_errors: list[str] = []
            for candidate_port in candidate_ports:
                self.debug_port = int(candidate_port)
                result = ChromeProcessManager.open_chrome_with_url(
                    profile_path,
                    bootstrap_url,
                    debug_port=self.debug_port,
                    profile_name=Path(profile_path).name,
                    headless=bool(self.headless),
                    hide_window=False,
                )
                if result is None:
                    launch_errors.append(f"{self.debug_port}: launch_failed")
                    continue
                if wait_for_cdp(f"http://{CDP_HOST}:{self.debug_port}", timeout_seconds=8):
                    break
                launch_errors.append(f"{self.debug_port}: cdp_timeout")
            else:
                details = ", ".join(launch_errors[:6]) or "khong_co_chi_tiet"
                raise RuntimeError(f"Khong the khoi dong Chrome dung chung cho Gemini. {details}")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.connect_over_cdp(
            f"http://{CDP_HOST}:{self.debug_port}"
        )
        self._connected_over_cdp = True
        self.context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        self.page = await self.context.new_page()
        self._owns_page = True

    async def _upload_local_file(self, video_path: str) -> bool:
        if self.page is None:
            return False

        try:
            locator = await self._find_matching_locator(
                GEMINI_UPLOAD_MENU_BUTTON_SELECTORS,
                state="visible",
                timeout_ms=5000,
                per_candidate_timeout_ms=500,
            )
            if locator is not None:
                chooser = None
                try:
                    async with self.page.expect_file_chooser(timeout=3000) as chooser_info:
                        try:
                            await locator.click(timeout=1500)
                        except Exception:
                            await locator.click(force=True, timeout=1500)
                    chooser = await chooser_info.value
                except Exception:
                    pass

                if chooser is not None:
                    await chooser.set_files(video_path)
                    await asyncio.sleep(8)
                    return True
                else:
                    if await self._trigger_upload_from_menu(video_path):
                        return True
        except Exception:
            pass

        trigger_selectors = [
            GEMINI_HIDDEN_FILE_UPLOAD_TRIGGER_SELECTOR,
        ]
        for selector in trigger_selectors:
            try:
                locator = await self._find_matching_locator(
                    [selector],
                    state="attached",
                    timeout_ms=2500,
                    per_candidate_timeout_ms=400,
                )
                if locator is None:
                    continue
                chooser = None
                try:
                    async with self.page.expect_file_chooser(timeout=3000) as chooser_info:
                        await locator.click(force=True, timeout=2000)
                    chooser = await chooser_info.value
                except Exception:
                    chooser = None

                if chooser is None:
                    async with self.page.expect_file_chooser(timeout=3000) as chooser_info:
                        await locator.evaluate("(node) => node.click()")
                    chooser = await chooser_info.value

                await chooser.set_files(video_path)
                await asyncio.sleep(10)
                return True
            except Exception:
                continue

        for selector in ['input[type="file"]']:
            try:
                collection = self.page.locator(selector)
                count = await collection.count()
                for i in range(min(count, 12)):
                    loc = collection.nth(i)
                    try:
                        async with self.page.expect_file_chooser(timeout=2000) as chooser_info:
                            await loc.evaluate("(node) => node.click()")
                        chooser = await chooser_info.value
                        await chooser.set_files(video_path)
                        await asyncio.sleep(8)
                        return True
                    except Exception:
                        pass
                    try:
                        await loc.set_input_files(video_path, timeout=1000)
                        await asyncio.sleep(8)
                        return True
                    except Exception:
                        pass
            except Exception:
                continue

        return False

    async def _find_matching_locator(
        self,
        selectors: list[str],
        *,
        state: str = "visible",
        timeout_ms: int = 8000,
        per_candidate_timeout_ms: int = 500,
        max_candidates_per_selector: int = 12,
    ):
        if self.page is None:
            return None

        deadline = asyncio.get_running_loop().time() + max(1.0, float(timeout_ms) / 1000.0)
        while asyncio.get_running_loop().time() < deadline:
            for selector in selectors:
                try:
                    collection = self.page.locator(selector)
                    count = await collection.count()
                except Exception:
                    continue

                for idx in range(min(count, max_candidates_per_selector)):
                    locator = collection.nth(idx)
                    try:
                        await locator.wait_for(state=state, timeout=per_candidate_timeout_ms)
                        return locator
                    except Exception:
                        continue
            await asyncio.sleep(0.2)
        return None

    async def _fill_prompt_input_text(self, text: str) -> bool:
        if self.page is None:
            return False

        locator = await self._find_matching_locator(
            GEMINI_PROMPT_EDITOR_SELECTORS,
            state="visible",
            timeout_ms=12000,
            per_candidate_timeout_ms=600,
        )
        if locator is None:
            return False

        try:
            await locator.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass

        try:
            await locator.click(force=True, timeout=2000)
        except Exception:
            try:
                await locator.evaluate("(node) => node.click()")
            except Exception:
                pass
        try:
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
        except Exception:
            pass
        normalized_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        expected_text = re.sub(r"\s+", " ", normalized_text).strip()

        async def _read_editor_text() -> str:
            try:
                current = await locator.evaluate(
                    """(node) => {
                        const text = String(node.innerText || node.textContent || "").replace(/\\u00a0/g, " ");
                        return text;
                    }"""
                )
            except Exception:
                return ""
            return re.sub(r"\s+", " ", str(current or "")).strip()

        try:
            await locator.evaluate(
                """(node) => {
                    node.focus();
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    range.collapse(true);
                    if (selection) {
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }
                }"""
            )
            await self.page.keyboard.insert_text(normalized_text)
            await asyncio.sleep(0.5)
            current_text = await _read_editor_text()
            if current_text and (current_text == expected_text or current_text.startswith(expected_text[: max(8, min(48, len(expected_text))) ])):
                return True
        except Exception:
            pass

        try:
            await locator.evaluate(
                """(node, value) => {
                    const text = String(value || "");
                    node.focus();
                    node.innerHTML = "";
                    try { node.classList.remove("ql-blank"); } catch (e) {}

                    const lines = text.split("\\n");
                    const frag = document.createDocumentFragment();
                    if (!lines.length) {
                        const p = document.createElement("p");
                        p.appendChild(document.createElement("br"));
                        frag.appendChild(p);
                    } else {
                        for (const line of lines) {
                            const p = document.createElement("p");
                            if (line) {
                                p.textContent = line;
                            } else {
                                p.appendChild(document.createElement("br"));
                            }
                            frag.appendChild(p);
                        }
                    }
                    node.replaceChildren(frag);
                    node.dispatchEvent(new InputEvent("input", {
                        bubbles: true,
                        cancelable: true,
                        inputType: "insertText",
                        data: text,
                    }));
                    node.dispatchEvent(new Event("change", { bubbles: true }));
                }""",
                normalized_text,
            )
        except Exception:
            return False
        await asyncio.sleep(0.4)
        current_text = await _read_editor_text()
        if not current_text:
            return False
        if not expected_text:
            return True
        if current_text == expected_text or current_text.startswith(expected_text[: max(8, min(48, len(expected_text))) ]):
            return True
        return False

    async def _click_send_button(self) -> bool:
        if self.page is None:
            return False

        deadline = asyncio.get_running_loop().time() + 12.0
        while asyncio.get_running_loop().time() < deadline:
            locator = await self._find_matching_locator(
                GEMINI_SEND_BUTTON_SELECTORS,
                state="visible",
                timeout_ms=1200,
                per_candidate_timeout_ms=250,
            )
            if locator is None:
                await asyncio.sleep(0.2)
                continue
            try:
                aria_disabled = str(await locator.get_attribute("aria-disabled") or "").strip().lower()
                disabled_attr = await locator.get_attribute("disabled")
                if aria_disabled == "true" or disabled_attr is not None:
                    await asyncio.sleep(0.2)
                    continue
                await locator.click()
                return True
            except Exception:
                await asyncio.sleep(0.2)
        return False

    async def _open_upload_menu(self) -> bool:
        if self.page is None:
            return False

        locator = await self._find_matching_locator(
            GEMINI_UPLOAD_MENU_BUTTON_SELECTORS,
            state="visible",
            timeout_ms=8000,
            per_candidate_timeout_ms=500,
        )
        if locator is None:
            return False
        try:
            await locator.click(timeout=2000)
        except Exception:
            await locator.click(force=True, timeout=2000)
        await asyncio.sleep(0.6)
        return True

    async def _trigger_upload_from_menu(self, video_path: str) -> bool:
        if self.page is None:
            return False

        for label in GEMINI_UPLOAD_MENU_ITEM_TEXTS:
            try:
                locator = await self._find_matching_locator(
                    [
                        f'button[role="menuitem"][data-test-id="local-images-files-uploader-button"][aria-label*="{label}"]',
                        'button[role="menuitem"][data-test-id="local-images-files-uploader-button"]',
                        '[role="menuitem"] div.menu-text.gem-menu-item-label',
                    ],
                    state="visible",
                    timeout_ms=4000,
                    per_candidate_timeout_ms=500,
                )
                if locator is None:
                    continue
                inner_text = str(await locator.inner_text() or "").strip().lower()
                if inner_text and label.lower() not in inner_text and "upload files" not in inner_text:
                    continue
                async with self.page.expect_file_chooser(timeout=4000) as chooser_info:
                    try:
                        await locator.click(timeout=2000)
                    except Exception:
                        await locator.click(force=True, timeout=2000)
                chooser = await chooser_info.value
                await chooser.set_files(video_path)
                await asyncio.sleep(10)
                return True
            except Exception:
                continue
        return False

    async def _wait_for_any_selector(
        self,
        selectors: list[str],
        *,
        state: str = "visible",
        timeout_ms: int = 15000,
    ) -> str | None:
        if self.page is None:
            return None

        deadline = asyncio.get_running_loop().time() + max(1.0, float(timeout_ms) / 1000.0)
        while asyncio.get_running_loop().time() < deadline:
            current_url = str(self.page.url or "").strip().lower()
            if "accounts.google.com" in current_url:
                raise RuntimeError("Chrome đang mở trang đăng nhập Google, chưa vào được Gemini.")

            locator = await self._find_matching_locator(
                selectors,
                state=state,
                timeout_ms=900,
                per_candidate_timeout_ms=250,
            )
            if locator is not None:
                return "matched"
            await asyncio.sleep(0.5)
        return None

    async def _open_gemini_app(self) -> None:
        if self.page is None:
            raise RuntimeError("Trang Gemini chưa được khởi tạo. Hãy gọi start() trước.")

        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                await self.page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=90000)
            except Exception as exc:
                last_error = exc

            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            try:
                await self.page.wait_for_load_state("load", timeout=5000)
            except Exception:
                pass

            ready = await self._wait_for_any_selector(
                GEMINI_READY_SELECTORS,
                state="attached",
                timeout_ms=30000,
            )
            if ready:
                return

            try:
                await self.page.reload(wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass

        if self.page:
            try:
                await self.page.screenshot(path="gemini_error_screenshot.png")
                content = await self.page.content()
                with open("gemini_error_page.html", "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass

        if last_error is not None:
            raise RuntimeError(f"Không mở được Gemini: {last_error}. (Đã lưu ảnh chụp lỗi tại gemini_error_screenshot.png)") from last_error
        raise RuntimeError("Không thấy giao diện Gemini sẵn sàng. (Đã lưu ảnh chụp lỗi tại gemini_error_screenshot.png)")

    async def _collect_response_texts(self) -> list[str]:
        if self.page is None:
            raise RuntimeError("Trang Gemini chưa được khởi tạo. Hãy gọi start() trước.")

        candidates = [
            ".model-response-text",
            "message-content",
            '[data-message-author-role="model"]',
            ".response-content",
            ".markdown",
        ]

        texts: list[str] = []
        for selector in candidates:
            try:
                locator = self.page.locator(selector)
                count = await locator.count()
            except Exception:
                count = 0
            if count <= 0:
                continue

            for idx in range(count):
                try:
                    text = str(await locator.nth(idx).inner_text(timeout=1000) or "").strip()
                except Exception:
                    continue
                if text:
                    texts.append(text)
        return texts

    async def _read_latest_response_text(self, timeout_ms: int = 90000, previous_texts: list[str] | None = None) -> str:
        seen = {str(text or "").strip() for text in (previous_texts or []) if str(text or "").strip()}
        deadline = asyncio.get_running_loop().time() + max(1.0, float(timeout_ms) / 1000.0)
        while asyncio.get_running_loop().time() < deadline:
            texts = await self._collect_response_texts()
            if texts:
                fresh = [text for text in texts if text not in seen]
                candidate_pool = fresh or texts
                for text in reversed(candidate_pool):
                    if "{" in text and "}" in text:
                        return text
                if fresh:
                    return fresh[-1]
            await asyncio.sleep(2)

        raise RuntimeError("Không tìm thấy phản hồi từ Gemini.")

    async def _read_latest_json_response_text(self, timeout_ms: int = 90000, previous_texts: list[str] | None = None) -> str:
        seen = {str(text or "").strip() for text in (previous_texts or []) if str(text or "").strip()}
        deadline = asyncio.get_running_loop().time() + max(1.0, float(timeout_ms) / 1000.0)
        last_text = ""
        while asyncio.get_running_loop().time() < deadline:
            texts = await self._collect_response_texts()
            if texts:
                fresh = [text for text in texts if text not in seen]
                candidate_pool = fresh or texts
                for text in reversed(candidate_pool):
                    last_text = str(text or "").strip() or last_text
                    parsed = self._extract_json_object(text)
                    if isinstance(parsed, dict):
                        return json.dumps(parsed, ensure_ascii=False)
            await asyncio.sleep(2)

        snippet = re.sub(r"\s+", " ", last_text).strip()[:300]
        if snippet:
            raise RuntimeError(f"Gemini có phản hồi nhưng chưa trả JSON hợp lệ. Mẫu cuối: {snippet}")
        raise RuntimeError("Không tìm thấy phản hồi JSON hợp lệ từ Gemini.")

    def _iter_json_object_candidates(self, raw_text: str) -> list[str]:
        text = str(raw_text or "").strip()
        if not text:
            return []

        candidates: list[str] = []
        if "```json" in text:
            try:
                fenced = text.split("```json", 1)[1].split("```", 1)[0].strip()
                if fenced:
                    candidates.append(fenced)
            except Exception:
                pass
        elif "```" in text:
            try:
                fenced = text.split("```", 1)[1].split("```", 1)[0].strip()
                if fenced:
                    candidates.append(fenced)
            except Exception:
                pass

        depth = 0
        start_idx: int | None = None
        in_string = False
        escape = False
        for idx, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                if depth == 0:
                    start_idx = idx
                depth += 1
                continue
            if ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        candidate = text[start_idx : idx + 1].strip()
                        if candidate:
                            candidates.append(candidate)
                        start_idx = None
        return candidates

    def _extract_json_object(self, raw_text: str) -> dict | None:
        for candidate in reversed(self._iter_json_object_candidates(raw_text)):
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _build_copy_video_prompt(self, target_language: str) -> str:
        normalized_target = normalize_locale(target_language) or "en-US"
        return (
            "Watch the uploaded video and act as a professional script analyst.\n"
            "Output ONLY a valid JSON object, no markdown, no commentary.\n"
            "Required schema_version: copy_video_pro_v5\n"
            "{\n"
            '  "schema_version": "copy_video_pro_v5",\n'
            '  "detected_source_language": "vi-VN",\n'
            f'  "target_language": "{normalized_target}",\n'
            '  "characters": [{"character_id": "char_01", "identity_lock_en": "stable technical appearance keywords"}],\n'
            '  "scenes": [\n'
            '    {\n'
            '      "scene_id": "scene_01",\n'
            '      "character_ids": ["char_01"],\n'
            '      "dialogue_original": "original spoken dialogue",\n'
            f'      "dialogue_target": "translated dialogue in {normalized_target}",\n'
            '      "video_prompt_en": "cinematic English action prompt",\n'
            '      "start_sec": 0.0,\n'
            '      "end_sec": 3.5\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Rules:\n"
            "1. Detect source language from the video.\n"
            f"2. Translate spoken dialogue to {normalized_target} and keep the original dialogue too.\n"
            "3. All appearance descriptions and visual actions must be in concise cinematic English.\n"
            "4. Reuse character_id consistently across scenes.\n"
            "5. If the video has no speech, keep dialogue fields as empty strings.\n"
            "6. Use as many scenes as needed, but keep the JSON compact and valid.\n"
        )

    def _build_copy_video_prompt_v2(
        self,
        target_language: str,
        style: str = "Tự động nhận diện",
        copy_strength: int = 100,
        user_edit_instruction: str = "",
    ) -> str:
        normalized_target = normalize_locale(target_language) or "en-US"
        normalized_strength = _normalize_copy_strength(copy_strength)
        clean_user_instruction = _normalize_user_edit_instruction(user_edit_instruction)
        style_instruction = ""
        if style != "Tự động nhận diện":
            style_instruction = f"\n13. CRITICAL: For 'style_block_en', you MUST use exactly the following style: '{style}'."
        else:
            style_instruction = "\n13. For 'style_block_en', automatically determine the best matching visual style based on the video."
        user_instruction_schema = ""
        user_instruction_rules = ""
        if clean_user_instruction:
            safe_instruction = json.dumps(clean_user_instruction, ensure_ascii=False)
            user_instruction_schema = '  "user_edit_instruction_en": "English version of the user edit instruction",\n'
            user_instruction_rules = (
                "\n14. USER EDIT INSTRUCTION: "
                f"{safe_instruction}\n"
                "- Apply this instruction consistently across character identity, scene planning, dialogue adaptation, and video_prompt_en.\n"
                "- Keep the source video's structure according to the copy strength, but this user instruction overrides the source's exact character/background details when they conflict.\n"
                "- Convert the user instruction into concise English in root user_edit_instruction_en.\n"
                "- Add custom_instruction_en to affected scenes so downstream video prompts keep the edit.\n"
            )
        else:
            user_instruction_rules = "\n14. No extra user edit instruction was provided; only follow copy strength and style rules."
        
        return (
            "You are Step0 source analysis for Video Composition.\n"
            "Analyze the uploaded video by watching the visuals and listening to the audio together.\n"
            "Your job is source understanding, copy-strength adaptation, and scene planning only.\n"
            "Return ONLY one valid JSON object.\n"
            "Do not use markdown.\n"
            "Do not wrap in code fences.\n"
            "Do not add explanations before or after JSON.\n"
            "Required schema_version: copy_video_pro_v5\n"
            "{\n"
            '  "schema_version": "copy_video_pro_v5",\n'
            f'  "copy_strength_percent": {normalized_strength},\n'
            f"{user_instruction_schema}"
            '  "detected_source_language": "vi-VN",\n'
            f'  "target_language": "{normalized_target}",\n'
            '  "characters": [\n'
            '    {\n'
            '      "character_id": "char_01",\n'
            '      "display_name": "Main Character",\n'
            '      "identity_lock_en": "stable English appearance lock for this recurring character"\n'
            '    }\n'
            '  ],\n'
            '  "scenes": [\n'
            '    {\n'
            '      "scene_id": "scene_01",\n'
            '      "character_ids": ["char_01"],\n'
            '      "dialogue_original": "original spoken dialogue",\n'
            f'      "dialogue_target": "translated dialogue in {normalized_target}",\n'
            '      "shot_type": "long shot",\n'
            '      "narrative_role": "opening",\n'
            '      "camera_angle": "eye-level",\n'
            '      "framing": "vertical 9:16 framing",\n'
            '      "lens_feel": "cinematic 2D lens feel",\n'
            '      "scene_action_en": "main action happening in this scene",\n'
            '      "environment_en": "background, location, and environmental details",\n'
            '      "mood_en": "scene mood and atmosphere",\n'
            '      "motion_en": "motion and animation details",\n'
            '      "style_block_en": "2D animation style, flat perspective with clean outlines, bold line art, and simplified forms",\n'
            '      "render_consistency_en": "consistent cel shading or flat coloring, no depth simulation",\n'
            '      "motion_style_en": "smooth but intentionally stylized, frame-by-frame animation feel",\n'
            '      "custom_instruction_en": "scene-specific English edit instruction if the user edit affects this scene",\n'
            '      "video_prompt_en": "cinematic English scene prompt for video generation",\n'
            '      "start_sec": 0.0,\n'
            '      "end_sec": 3.5\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Rules:\n"
            "1. Segment the video into clear short scenes, ideally around 4 to 8 seconds each.\n"
            "2. Detect the source language from spoken audio or visible subtitles.\n"
            f"3. For close copy levels, translate spoken dialogue to {normalized_target} and keep the original dialogue too. For 50%-60%, make dialogue_target adapted/new dialogue in {normalized_target} that preserves intent, not a literal copy.\n"
            "4. All character appearance descriptions and all visual scene fields must be written in clear cinematic English.\n"
            "5. Reuse the same character_id consistently across scenes.\n"
            "6. shot_type, camera_angle, framing, and lens_feel must be concise film-style descriptors.\n"
            "7. scene_action_en must describe only the core visible action of that scene.\n"
            "8. environment_en, mood_en, and motion_en must be concise and production-friendly.\n"
            "9. If the video has no dialogue in a scene, use empty strings for dialogue fields.\n"
            "10. Output compact JSON only.\n"
            "11. Apply the copy strength profile below when deciding how closely to mirror the source.\n"
            "12. The scenes must form a full short-video arc: opening, body/development, and ending/resolution. If the source is too short, create concise adapted beats to complete the arc.\n"
            f"{style_instruction}\n"
            f"{user_instruction_rules}\n"
            f"{_copy_strength_prompt_block(normalized_strength)}\n"
        )

    def _build_character_design_prompt(self, source_data: dict) -> str:
        source_json = json.dumps(source_data or {}, ensure_ascii=False, indent=2)
        copy_strength = _normalize_copy_strength((source_data or {}).get("copy_strength_percent") or 100)
        has_user_instruction = bool(
            _normalize_user_edit_instruction(
                (source_data or {}).get("user_edit_instruction_en")
                or (source_data or {}).get("user_edit_instruction")
            )
        )
        if has_user_instruction:
            character_copy_rule = (
                "9. User edit instruction is present: apply it before copy-strength preservation. "
                "Preserve only the unaffected source identity details; change any face, body, wardrobe, age, gender, role, or styling details required by the user edit."
            )
        elif copy_strength <= 60:
            character_copy_rule = (
                "9. Copy strength is low: design original characters inspired only by the role/archetype. "
                "Do not replicate exact faces, outfits, accessories, or other identifying details from the source."
            )
        elif copy_strength < 100:
            character_copy_rule = (
                "9. Copy strength is partial: keep character roles recognizable, but vary non-essential face, wardrobe, and accessory details."
            )
        else:
            character_copy_rule = "9. Copy strength is 100%: preserve visible character identity as closely as the source analysis allows."
        return (
            "You are Character Design Planner for a video generation workflow.\n"
            "Based on the source analysis JSON below, design consistent production-ready character reference plans.\n"
            "This is a planning-only task.\n"
            "Return ONLY one valid JSON object.\n"
            "Do not use markdown.\n"
            "Do not wrap in code fences.\n"
            "Do not add explanations before or after JSON.\n"
            "Required schema_version: copy_video_character_design_v1\n"
            "{\n"
            '  "schema_version": "copy_video_character_design_v1",\n'
            '  "characters": [\n'
            '    {\n'
            '      "character_id": "char_01",\n'
            '      "display_name": "Zen Scholar",\n'
            '      "role": "main",\n'
            '      "identity_lock_en": "master identity lock for full consistency",\n'
            '      "face_design_en": "face shape, eyes, nose, mouth, age cues",\n'
            '      "hair_design_en": "hair shape, texture, hairline, length, color",\n'
            '      "body_design_en": "height, build, posture, silhouette",\n'
            '      "wardrobe_en": "full clothing design with materials and colors",\n'
            '      "color_palette_en": "dominant color palette for the character",\n'
            '      "reference_sheet_prompt_en": "landscape character reference sheet, four-angle turnaround, front left right back, full-body concept sheet, clean white background",\n'
            '      "turnaround_prompts_en": {\n'
            '        "front": "front full-body character sheet prompt",\n'
            '        "left": "left side character sheet prompt",\n'
            '        "right": "right side character sheet prompt",\n'
            '        "back": "back full-body character sheet prompt"\n'
            '      }\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Rules:\n"
            "1. Preserve the same character_id values from the source analysis JSON.\n"
            "2. Do not invent unnecessary new characters.\n"
            "3. Make each character visually stable and production-ready.\n"
            "4. Write all design fields in clear English optimized for image generation.\n"
            "5. reference_sheet_prompt_en must create one single landscape image containing front, left, right, and back full-body turnaround views of the same character.\n"
            "6. turnaround_prompts_en must be suitable for generating clean character reference images.\n"
            "7. Focus on consistency, silhouette clarity, outfit repeatability, and face identity stability.\n"
            "8. Output compact JSON only.\n"
            f"{character_copy_rule}\n"
            "10. If the source analysis contains user_edit_instruction_en, the character designs MUST obey it consistently.\n"
            "\n"
            "Source analysis JSON:\n"
            f"{source_json}"
        )

    def _build_json_repair_prompt(self) -> str:
        return (
            "Your previous response was not a valid JSON object.\n"
            "Return ONLY one valid JSON object for the previous task.\n"
            "Do not add explanations.\n"
            "Do not use markdown.\n"
            "Do not wrap the JSON in code fences.\n"
        )

    async def _submit_prompt_and_wait_json(self, prompt_text: str, previous_texts: list[str] | None = None) -> dict:
        if not await self._fill_prompt_input_text(prompt_text):
            raise RuntimeError("Không tìm thấy ô nhập prompt trên Gemini.")
        if not await self._click_send_button():
            await self.page.keyboard.press("Enter")

        raw_text = await self._read_latest_json_response_text(previous_texts=previous_texts)
        json_text = self._extract_json_text(raw_text)
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            raise RuntimeError("Phản hồi từ Gemini không phải JSON object hợp lệ.")
        return parsed

    async def _submit_prompt_and_wait_json_with_retry(self, prompt_text: str, previous_texts: list[str] | None = None) -> dict:
        try:
            return await self._submit_prompt_and_wait_json(prompt_text, previous_texts=previous_texts)
        except Exception:
            retry_previous_texts = await self._collect_response_texts()
            return await self._submit_prompt_and_wait_json(
                self._build_json_repair_prompt(),
                previous_texts=retry_previous_texts,
            )

    async def _run_json_prompt_in_new_chat(self, prompt_text: str) -> dict:
        if self.context is None:
            raise RuntimeError("Chưa có context Gemini để mở cuộc trò chuyện mới.")

        original_page = self.page
        new_page = await self.context.new_page()
        try:
            self.page = new_page
            await self._open_gemini_app()
            previous_texts = await self._collect_response_texts()
            return await self._submit_prompt_and_wait_json_with_retry(prompt_text, previous_texts=previous_texts)
        finally:
            self.page = original_page
            try:
                if not new_page.is_closed():
                    await new_page.close()
            except Exception:
                pass

    def _extract_json_text(self, raw_text: str) -> str:
        parsed = self._extract_json_object(raw_text)
        if isinstance(parsed, dict):
            return json.dumps(parsed, ensure_ascii=False)
        return str(raw_text or "").strip()

    async def analyze_video(self, video_path: str, target_language: str = "en-US") -> dict:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy tệp video: {video_path}")
        if self.page is None:
            raise RuntimeError("Trang Gemini chưa được khởi tạo. Hãy gọi start() trước.")

        await self._open_gemini_app()

        try:
            previous_texts = await self._collect_response_texts()
            if not await self._upload_local_file(video_path):
                raise RuntimeError(
                    "Không tìm thấy nút kích hoạt upload ẩn. Selector kỳ vọng: "
                    f"{GEMINI_HIDDEN_FILE_UPLOAD_TRIGGER_SELECTOR}"
                )

            prompt = self._build_copy_video_prompt_v2(target_language)
            if not await self._fill_prompt_input_text(prompt):
                raise RuntimeError("Không tìm thấy ô nhập prompt trên Gemini.")
            if not await self._click_send_button():
                await self.page.keyboard.press("Enter")

            raw_text = await self._read_latest_json_response_text(previous_texts=previous_texts)
            json_text = self._extract_json_text(raw_text)
            parsed = json.loads(json_text)
            if not isinstance(parsed, dict):
                raise RuntimeError("Phản hồi từ Gemini không phải JSON object hợp lệ.")
            return _normalize_copy_video_payload(parsed, target_language, copy_strength=100)
        except Exception as exc:
            raise RuntimeError(f"Lỗi tự động hóa Gemini: {exc}") from exc

    async def analyze_video_v2(
        self,
        video_path: str,
        target_language: str = "en-US",
        style: str = "Tự động nhận diện",
        copy_strength: int = 100,
        user_edit_instruction: str = "",
    ) -> dict:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy tệp video: {video_path}")
        if self.page is None:
            raise RuntimeError("Trang Gemini chưa được khởi tạo. Hãy gọi start() trước.")

        await self._open_gemini_app()

        try:
            self._log("🧠 Bước 1/2: phân tích video nguồn và chia cảnh...")
            previous_texts = await self._collect_response_texts()
            if not await self._upload_local_file(video_path):
                raise RuntimeError("Không tìm thấy nút upload để gửi video nguồn lên Gemini.")

            parsed = await self._submit_prompt_and_wait_json_with_retry(
                self._build_copy_video_prompt_v2(
                    target_language,
                    style=style,
                    copy_strength=copy_strength,
                    user_edit_instruction=user_edit_instruction,
                ),
                previous_texts=previous_texts,
            )
            source_data = _normalize_copy_video_payload(
                parsed,
                target_language,
                copy_strength=copy_strength,
                user_edit_instruction=user_edit_instruction,
            )
            characters = source_data.get("characters") if isinstance(source_data.get("characters"), list) else []
            if not characters:
                return source_data

            try:
                self._log("👤 Bước 2/2: mở cuộc trò chuyện Gemini mới để thiết kế nhân vật...")
                design_raw = await self._run_json_prompt_in_new_chat(
                    self._build_character_design_prompt(source_data)
                )
                design_data = _normalize_character_design_payload(design_raw, characters)
                merged = _merge_character_design_into_source(source_data, design_data)
                self._log(f"✅ Đã thiết kế nhân vật: {len(design_data.get('characters') or [])} hồ sơ nhân vật.")
                return merged
            except Exception as design_exc:
                self._log(f"⚠️ Bỏ qua bước thiết kế nhân vật tự động: {design_exc}")
                return source_data
        except Exception as exc:
            raise RuntimeError(f"Lỗi tự động hóa Gemini: {exc}") from exc

    async def close(self):
        page = self.page
        playwright = self.playwright
        owns_page = bool(self._owns_page)

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._owns_page = False

        try:
            if page is not None and owns_page:
                try:
                    if not page.is_closed():
                        await page.close()
                except Exception:
                    pass

            # Với browser attach qua CDP dùng chung, không gọi browser.close()
            # vì có thể đóng luôn Chrome render chung của ứng dụng.
            await asyncio.sleep(0)
        finally:
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass
            self._connected_over_cdp = False
