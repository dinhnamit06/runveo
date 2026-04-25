# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import importlib.util
import json
import math
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

import imageio_ffmpeg

from src.utils.voice_profiles import VOICE_JSON

from src.utils.tts_voices import (
    EDGE_TTS_DEFAULT,
    TIKTOK_TTS_DEFAULT,
    get_edge_tts_voice_metadata,
    is_edge_tts_voice_key,
    is_tiktok_tts_voice_key,
)
from src.features.tiktok_tts_exporter import tiktok_tts_save
from src.core.settings_manager import SettingsManager



FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


EDGE_TTS_VOICE_BY_LOCALE_GENDER = {
    ("vi-VN", "female"): "vi-VN-HoaiMyNeural",
    ("vi-VN", "male"): "vi-VN-NamMinhNeural",
    ("en-US", "female"): "en-US-JennyNeural",
    ("en-US", "male"): "en-US-GuyNeural",
    ("en-GB", "female"): "en-GB-SoniaNeural",
    ("en-GB", "male"): "en-GB-RyanNeural",
    ("ja-JP", "female"): "ja-JP-NanamiNeural",
    ("ja-JP", "male"): "ja-JP-KeitaNeural",
    ("ko-KR", "female"): "ko-KR-SunHiNeural",
    ("ko-KR", "male"): "ko-KR-InJoonNeural",
    ("zh-CN", "female"): "zh-CN-XiaoxiaoNeural",
    ("zh-CN", "male"): "zh-CN-YunxiNeural",
}


def _win_hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return {"startupinfo": si, "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    except Exception:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_win_hidden_kwargs(),
    )


def _safe_stem(text: str, fallback: str = "storytelling") -> str:
    raw = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(text or ""))
    raw = "_".join(part for part in raw.split("_") if part)
    return (raw or fallback)[:90]


def _voice_name(voice_key: str) -> str:
    raw_key = str(voice_key or "").strip()
    if is_edge_tts_voice_key(raw_key):
        return raw_key or EDGE_TTS_DEFAULT
    meta = VOICE_JSON.get(str(voice_key or ""), {}) if isinstance(VOICE_JSON, dict) else {}
    locale = str(meta.get("locale") or "vi-VN")
    gender = str(meta.get("gender") or "female").lower()
    if gender not in {"male", "female"}:
        gender = "female"
    return EDGE_TTS_VOICE_BY_LOCALE_GENDER.get((locale, gender)) or EDGE_TTS_VOICE_BY_LOCALE_GENDER.get((locale, "female")) or "vi-VN-HoaiMyNeural"


def _normalize_tts_provider(value: str | None) -> str:
    provider = str(value or "auto").strip().lower()
    if provider in {"edge_tts", "edge-tts", "edge"}:
        return "edge"
    if provider in {"windows", "windows_sapi", "sapi"}:
        return "sapi"
    if provider in {"none", "no", "off", "silent"}:
        return "off"
    if provider == "voicebox":
        return "voicebox"
    if provider == "tiktok":
        return "tiktok"
    return "auto" 


def is_edge_tts_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def _estimate_duration(text: str) -> float:
    words = max(1, len(str(text or "").split()))
    return max(3.5, min(18.0, (words / 2.55) + 1.2))


def _probe_duration(path: str) -> float:
    if not path or not os.path.isfile(path):
        return 0.0
    cmd = [FFMPEG_PATH, "-i", str(path)]
    ret = _run(cmd)
    text = f"{ret.stdout or ''}\n{ret.stderr or ''}"
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return 0.0
    try:
        hours = float(match.group(1))
        minutes = float(match.group(2))
        seconds = float(match.group(3))
        return max(0.0, (hours * 3600.0) + (minutes * 60.0) + seconds)
    except Exception:
        return 0.0


async def _edge_tts_save(text: str, out_path: str, voice_name: str) -> bool:
    try:
        import edge_tts  # type: ignore
    except Exception:
        return False
    try:
        communicate = edge_tts.Communicate(str(text or ""), voice_name)
        await communicate.save(str(out_path))
        return os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _voicebox_tts_save(text: str, out_path: str, voice_id: str) -> bool:
    import urllib.request
    import urllib.error
    import json
    
    ports = [17493, 8000]
    for port in ports:
        url = f"http://localhost:{port}/generate"
        data = json.dumps({"text": text, "voice_id": voice_id}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                # Check if it returns an audio file directly or an ID to poll
                if isinstance(result, dict) and 'generation_id' in result:
                    gen_id = result['generation_id']
                    # Simplified: wait for it (would need proper polling endpoint usually)
                    pass
                elif isinstance(result, dict) and 'audio_url' in result:
                    audio_req = urllib.request.urlopen(result['audio_url'])
                    with open(out_path, 'wb') as out_f:
                        out_f.write(audio_req.read())
                    return True
                else:
                    # Maybe it returns raw audio?
                    pass
        except Exception:
            pass
            
        # Try OpenAI compatible endpoint just in case
        url = f"http://localhost:{port}/v1/audio/speech"
        data = json.dumps({"model": "voicebox", "input": text, "voice": voice_id}).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(out_path, 'wb') as out_f:
                    out_f.write(response.read())
                return os.path.isfile(out_path) and os.path.getsize(out_path) > 0
        except Exception:
            pass
            
    return False

def _sapi_tts_save(text: str, out_path: str, voice_key: str) -> bool:
    if os.name != "nt":
        return False
    ps_path = ""
    try:
        meta = VOICE_JSON.get(str(voice_key or ""), {}) if isinstance(VOICE_JSON, dict) else {}
        if not meta and is_edge_tts_voice_key(voice_key):
            meta = get_edge_tts_voice_metadata(voice_key)
        gender = str(meta.get("gender") or "").lower()
        gender_hint = "Female" if gender == "female" else "Male" if gender == "male" else "NotSet"
        script = f"""
Add-Type -AssemblyName System.Speech
$text = {json.dumps(str(text or ""), ensure_ascii=False)}
$out = {json.dumps(str(out_path), ensure_ascii=False)}
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
  if ({json.dumps(gender_hint)} -ne "NotSet") {{
    $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::{gender_hint})
  }}
}} catch {{}}
$synth.Rate = 0
$synth.Volume = 100
$synth.SetOutputToWaveFile($out)
$synth.Speak($text)
$synth.Dispose()
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", suffix=".ps1", delete=False) as tf:
            ps_path = tf.name
            tf.write(script)
        ret = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path])
        return ret.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False
    finally:
        if ps_path and os.path.isfile(ps_path):
            try:
                os.remove(ps_path)
            except Exception:
                pass


def _silent_audio(out_path: str, duration: float) -> bool:
    cmd = [
        FFMPEG_PATH,
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t",
        f"{max(1.0, float(duration)):.3f}",
        "-c:a",
        "aac",
        "-y",
        str(out_path),
    ]
    ret = _run(cmd)
    return ret.returncode == 0 and os.path.isfile(out_path)


def _make_audio(
    text: str,
    out_dir: Path,
    idx: int,
    voice_key: str,
    *,
    tts_provider: str = "auto",
    log: Callable[[str], None] | None = None,
) -> tuple[str, float]:
    clean_text = str(text or "").strip()
    duration_hint = _estimate_duration(clean_text)
    provider = _normalize_tts_provider(tts_provider)
    raw_voice_key = str(voice_key or "").strip()
    if provider == "tiktok" and not is_tiktok_tts_voice_key(raw_voice_key):
        provider = "edge" if is_edge_tts_voice_key(raw_voice_key) else "auto"
    voice_name = _voice_name(raw_voice_key)
    edge_path = str(out_dir / f"audio_{idx:03d}.mp3")
    wav_path = str(out_dir / f"audio_{idx:03d}.wav")
    silent_path = str(out_dir / f"audio_{idx:03d}_silent.m4a")

    if provider == "off" or raw_voice_key == "None_NoVoice":
        _silent_audio(silent_path, duration_hint)
        return silent_path, duration_hint


    if clean_text:
        is_tiktok = provider == "tiktok" or is_tiktok_tts_voice_key(raw_voice_key)
        
        if is_tiktok:
            try:
                cfg = SettingsManager.load_config()
                if not isinstance(cfg, dict): cfg = {}
                session_id = str(cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id") or "").strip()
                ok = tiktok_tts_save(clean_text, edge_path, raw_voice_key, session_id)
            except Exception as exc:
                if callable(log): log(f"Lỗi Tiktok TTS: {exc}")
                ok = False
            
            if ok:
                duration = _probe_duration(edge_path) or duration_hint
                return edge_path, duration
            else:
                if callable(log):
                    log("⚠️ Tiktok TTS lỗi hoặc thiếu Session ID; chuyển sang audio im lặng.")
                _silent_audio(silent_path, duration_hint)
                return silent_path, duration_hint

        try:

            ok = provider in {"auto", "edge"} and asyncio.run(_edge_tts_save(clean_text, edge_path, voice_name))
        except Exception:
            ok = False
        if ok:
            duration = _probe_duration(edge_path) or duration_hint
            return edge_path, duration
        if provider == "edge" and callable(log):
            log("⚠️ Edge TTS chưa khả dụng hoặc không tạo được audio; dùng audio im lặng cho cảnh này.")
            _silent_audio(silent_path, duration_hint)
            return silent_path, duration_hint

        if provider in {"auto", "sapi"} and _sapi_tts_save(clean_text, wav_path, voice_key):
            duration = _probe_duration(wav_path) or duration_hint
            return wav_path, duration
        if provider == "sapi" and callable(log):
            log("⚠️ Windows SAPI không tạo được audio; dùng audio im lặng cho cảnh này.")
            _silent_audio(silent_path, duration_hint)
            return silent_path, duration_hint

    if callable(log):
        log(f"⚠️ Không tạo được voice TTS cho cảnh {idx}; dùng audio im lặng để không lỗi xuất video.")
    _silent_audio(silent_path, duration_hint)
    return silent_path, duration_hint


def create_tts_preview(
    text: str,
    out_dir: str,
    *,
    voice_key: str,
    tts_provider: str = "edge",
) -> str:
    provider = _normalize_tts_provider(tts_provider)
    if provider == "tiktok" and not is_tiktok_tts_voice_key(voice_key):
        provider = "edge" if is_edge_tts_voice_key(voice_key) else "auto"
    if provider == "off":
        raise RuntimeError("TTS đang tắt, không có giọng để nghe thử.")
    if provider == "edge" and not is_edge_tts_available():
        raise RuntimeError("Chưa cài edge-tts. Cài bằng: python -m pip install edge-tts")
    if provider == "tiktok":
        cfg = SettingsManager.load_config()
        if not isinstance(cfg, dict):
            cfg = {}
        session_id = str(cfg.get("TIKTOK_SESSION_ID") or cfg.get("tiktok_session_id") or "").strip()
        if not session_id:
            raise RuntimeError("Thiếu TikTok SessionID. Vào Cài đặt và dán sessionid trước khi nghe thử CapCut/TikTok TTS.")

    out_root = Path(out_dir or tempfile.gettempdir()) / "veo_tts_preview"
    out_root.mkdir(parents=True, exist_ok=True)
    
    import hashlib
    import shutil
    clean_text = str(text or "Xin chào, đây là giọng đọc thử.").strip()
    cache_voice_key = str(voice_key or "")
    if provider == "tiktok":
        try:
            from src.features.tiktok_tts_exporter import get_tiktok_voice_id

            cache_voice_key = f"{cache_voice_key}:{get_tiktok_voice_id(cache_voice_key)}"
        except Exception:
            cache_voice_key = f"{cache_voice_key}:tiktok"
    cache_key = hashlib.md5(f"{clean_text}_{cache_voice_key}_{provider}_v2".encode("utf-8")).hexdigest()
    cached_path = out_root / f"preview_{cache_key}.wav"
    
    if cached_path.is_file() and cached_path.stat().st_size > 4096:
        return str(cached_path)
        
    audio_path, _duration = _make_audio(
        clean_text,
        out_root,
        1,
        voice_key,
        tts_provider=provider,
    )
    if not os.path.isfile(audio_path):
        raise RuntimeError("Không tạo được file nghe thử TTS.")
    if provider == "tiktok" and str(audio_path).endswith("_silent.m4a"):
        raise RuntimeError("CapCut/TikTok TTS không tạo được audio. Kiểm tra lại SessionID hoặc thử giọng khác.")
        
    try:
        if str(audio_path).lower().endswith(".wav"):
            shutil.copy2(audio_path, cached_path)
            return str(cached_path)
        ret = _run([
            FFMPEG_PATH,
            "-y",
            "-i",
            str(audio_path),
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(cached_path),
        ])
        if ret.returncode == 0 and cached_path.is_file() and cached_path.stat().st_size > 4096:
            return str(cached_path)
    except Exception:
        pass
    return audio_path



def _resolution(aspect_ratio: str) -> tuple[int, int]:
    return (1920, 1080) if str(aspect_ratio or "9:16").strip() == "16:9" else (1080, 1920)


def _make_motion_clip(image_path: str, audio_path: str, out_path: str, duration: float, aspect_ratio: str, enable_motion: bool = True) -> None:
    width, height = _resolution(aspect_ratio)
    fps = 30
    frames = max(1, int(math.ceil(max(1.0, float(duration)) * fps)))
    if enable_motion:
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.06)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={width}x{height}:fps={fps},"
            "format=yuv420p"
        )
    else:
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            "format=yuv420p"
        )
    cmd = [
        FFMPEG_PATH,
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-vf",
        vf,
        "-frames:v",
        str(frames),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-shortest",
        "-movflags",
        "+faststart",
        "-y",
        str(out_path),
    ]
    ret = _run(cmd)
    if ret.returncode != 0 or not os.path.isfile(out_path):
        err = (ret.stderr or "Unknown FFmpeg error")[-700:]
        raise RuntimeError(f"Tạo clip storytelling thất bại: {err}")


def _concat_clips(clips: list[str], out_path: str) -> str:
    list_file = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
            list_file = tf.name
            for clip in clips:
                safe = Path(clip).resolve().as_posix().replace("'", "'\\''")
                tf.write(f"file '{safe}'\n")
        cmd = [
            FFMPEG_PATH,
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(out_path),
        ]
        ret = _run(cmd)
        if ret.returncode != 0 or not os.path.isfile(out_path):
            err = (ret.stderr or "Unknown FFmpeg error")[-700:]
            raise RuntimeError(f"Ghép storytelling video thất bại: {err}")
        return out_path
    finally:
        if list_file and os.path.isfile(list_file):
            try:
                os.remove(list_file)
            except Exception:
                pass


def export_storytelling_video(
    items: list[dict],
    output_dir: str,
    *,
    voice_key: str = "None_NoVoice",
    tts_provider: str = "auto",
    aspect_ratio: str = "9:16",
    enable_motion: bool = True,
    log_callback: Callable[[str], None] | None = None,
) -> str:
    clean_items: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        image_path = str(item.get("image_path") or "").strip()
        if not image_path or not os.path.isfile(image_path):
            continue
        narration = str(item.get("narration") or item.get("text") or "").strip()
        clean_items.append({"image_path": image_path, "narration": narration})

    if not clean_items:
        raise ValueError("Không có ảnh hợp lệ để xuất Storytelling.")

    out_root = Path(output_dir or ".")
    out_root.mkdir(parents=True, exist_ok=True)
    work_dir = out_root / "storytelling_tmp" / datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir.mkdir(parents=True, exist_ok=True)
    clips: list[str] = []

    def log(msg: str) -> None:
        if callable(log_callback):
            log_callback(str(msg or ""))

    for idx, item in enumerate(clean_items, start=1):
        log(f"🎙️ Đang tạo audio cảnh {idx}/{len(clean_items)}...")
        audio_path, duration = _make_audio(
            item["narration"],
            work_dir,
            idx,
            voice_key,
            tts_provider=tts_provider,
            log=log,
        )
        
        log(f"🎬 Đang xử lý chuyển động ảnh và ghép audio cảnh {idx}/{len(clean_items)}...")
        clip_path = str(work_dir / f"clip_{idx:03d}.mp4")
        _make_motion_clip(item["image_path"], audio_path, clip_path, duration, aspect_ratio, enable_motion)
        clips.append(clip_path)
        log(f"✅ Hoàn thành cảnh {idx}/{len(clean_items)}")

    out_path = str(out_root / f"storytelling_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    return _concat_clips(clips, out_path)
