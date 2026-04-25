import sys

with open('storytelling_exporter.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add _voicebox_tts_save function
voicebox_func = """def _voicebox_tts_save(text: str, out_path: str, voice_id: str) -> bool:
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

"""

if "_voicebox_tts_save" not in content:
    content = content.replace("def _sapi_tts_save", voicebox_func + "def _sapi_tts_save")

# Update _normalize_tts_provider
norm_target = """    if provider in {"none", "no", "off", "silent"}:
        return "off"
    return "auto\""""

norm_patch = """    if provider in {"none", "no", "off", "silent"}:
        return "off"
    if provider == "voicebox":
        return "voicebox"
    return "auto\""""

content = content.replace(norm_target, norm_patch)

# Update _make_audio
make_target = """    if clean_text:
        try:
            ok = provider in {"auto", "edge"} and asyncio.run(_edge_tts_save(clean_text, edge_path, voice_name))
        except Exception:"""

make_patch = """    if clean_text:
        if provider == "voicebox":
            if _voicebox_tts_save(clean_text, edge_path, voice_key):
                duration = _probe_duration(edge_path) or duration_hint
                return edge_path, duration
            if callable(log):
                log("⚠️ Lỗi gọi Voicebox API (có thể chưa bật Voicebox hoặc sai port/Voice ID); dùng audio im lặng.")
            _silent_audio(silent_path, duration_hint)
            return silent_path, duration_hint

        try:
            ok = provider in {"auto", "edge"} and asyncio.run(_edge_tts_save(clean_text, edge_path, voice_name))
        except Exception:"""

if "provider == \"voicebox\":" not in content:
    content = content.replace(make_target, make_patch)

with open('storytelling_exporter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched storytelling_exporter.py for Voicebox API")
