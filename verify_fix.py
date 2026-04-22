import asyncio
import re
from pathlib import Path

# Mock parts of the workflow to verify logic
def mock_build_candidate_urls(media_url, parent_id):
    candidate_urls = []
    if media_url:
        candidate_urls.append(media_url)
    
    user_id = ""
    generated_id = (parent_id or "").strip()
    if media_url:
        m = re.search(r"/users/([^/]+)/generated/([^/]+)/", str(media_url))
        if m:
            user_id = m.group(1).strip()
            if not generated_id:
                generated_id = m.group(2).strip()

    if user_id and generated_id:
        candidate_urls.append(f"https://assets.grok.com/users/{user_id}/generated/{generated_id}/generated_video_hd.mp4?cache=1&dl=1")
        candidate_urls.append(f"https://assets.grok.com/users/{user_id}/generated/{generated_id}/generated_video.mp4?cache=1&dl=1")
    
    return [str(u).strip() for u in candidate_urls]

def test_logic():
    # Test 1: Standard response with user_id and gid
    media = "https://assets.grok.com/users/user_123/generated/vid_456/generated_video.mp4"
    pid = "vid_456"
    candidates = mock_build_candidate_urls(media, pid)
    print(f"Test 1 Candidates: {candidates}")
    assert len(candidates) >= 3
    assert "generated_video_hd.mp4" in candidates[1]
    assert "generated_video.mp4" in candidates[2]

    # Test 2: Native 10s generation where parent_id is available but media_url might be different
    media = "https://assets.grok.com/users/super_user/generated/long_vid_789/temp_preview.mp4"
    pid = "long_vid_789"
    candidates = mock_build_candidate_urls(media, pid)
    print(f"Test 2 Candidates: {candidates}")
    assert any("generated_video.mp4" in c for c in candidates)
    
    print("\n✅ Verification script logic passed!")

if __name__ == "__main__":
    test_logic()
