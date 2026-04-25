# Patch voice_profiles.py
with open('voice_profiles.py', 'r', encoding='utf-8') as f:
    content = f.read()

tiktok_voices = """
    "tiktok_vn_female_1": {
        "label": "Tiktok Nữ miền Nam",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "tiktok",
        "priority": 110,
        "enabled": True,
        "aliases": ["vi", "vi_VN", "tiktok"],
        "fallback_locales": ["en-US"],
        "voice_profile": "vn_001_female"
    },
    "tiktok_vn_male_1": {
        "label": "Tiktok Nam miền Nam",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "tiktok",
        "priority": 109,
        "enabled": True,
        "aliases": ["vi", "vi_VN", "tiktok"],
        "fallback_locales": ["en-US"],
        "voice_profile": "vn_002_male"
    },
    "tiktok_vn_female_2": {
        "label": "Tiktok Nữ miền Bắc",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "female",
        "style": "tiktok",
        "priority": 108,
        "enabled": True,
        "aliases": ["vi", "vi_VN", "tiktok"],
        "fallback_locales": ["en-US"],
        "voice_profile": "vn_003_female"
    },
    "tiktok_vn_male_2": {
        "label": "Tiktok Nam miền Bắc",
        "locale": "vi-VN",
        "language": "vi",
        "gender": "male",
        "style": "tiktok",
        "priority": 107,
        "enabled": True,
        "aliases": ["vi", "vi_VN", "tiktok"],
        "fallback_locales": ["en-US"],
        "voice_profile": "vn_004_male"
    },"""

if '"tiktok_vn_female_1"' not in content:
    content = content.replace('"Nam_Kechuyen": {', tiktok_voices + '\n    "Nam_Kechuyen": {')

with open('voice_profiles.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Patch ui.py
with open('ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

if "tiktok_session_id" not in content:
    content = content.replace('multi_video: int = 3', 'tiktok_session_id: str = ""\n    multi_video: int = 3')
    
    content = content.replace('cfg.output_count = int(', 'cfg.tiktok_session_id = str(data.get("TIKTOK_SESSION_ID", cfg.tiktok_session_id) or "")\n                cfg.output_count = int(')
    
    content = content.replace('"GROK_ACCOUNT_TYPE": grok_account_type,', '"GROK_ACCOUNT_TYPE": grok_account_type,\n            "TIKTOK_SESSION_ID": str(self.tiktok_session_id or ""),')

with open('ui.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Patch tab_settings.py
with open('tab_settings.py', 'r', encoding='utf-8') as f:
    content = f.read()

if "tiktok_session_id" not in content:
    tt_ui = """
        self.tiktok_session_id = QLineEdit(str(getattr(config, "tiktok_session_id", "") or ""))
        self.tiktok_session_id.setFixedHeight(34)
        self.tiktok_session_id.setPlaceholderText("Dán sessionid từ Cookie Tiktok (vd: 574742a...)")
        form.addRow("Tiktok SessionID:", self.tiktok_session_id)
        
        self.btn_guide_tiktok = QPushButton("Hướng dẫn lấy mã Tiktok")
        self.btn_guide_tiktok.setStyleSheet("color: blue; text-decoration: underline; border: none; background: transparent; text-align: left;")
        self.btn_guide_tiktok.clicked.connect(self._guide_tiktok)
        form.addRow("", self.btn_guide_tiktok)
"""
    content = content.replace('form.addRow("Giọng đọc:", self.voice_profile)', 'form.addRow("Giọng đọc:", self.voice_profile)' + tt_ui)
    
    save_logic = """
        setattr(self._cfg, "veo3_user", self.veo3_user.text().strip())
        setattr(self._cfg, "tiktok_session_id", self.tiktok_session_id.text().strip())"""
    content = content.replace('setattr(self._cfg, "veo3_user", self.veo3_user.text().strip())', save_logic)
    
    guide_logic = """
    def _guide_tiktok(self) -> None:
        msg = "CÁCH LẤY TIKTOK SESSION ID:\\n\\n1. Mở trình duyệt Chrome và truy cập tiktok.com\\n2. Đăng nhập vào tài khoản Tiktok của bạn.\\n3. Nhấn phím F12 để mở Công cụ dành cho nhà phát triển (Developer Tools).\\n4. Chuyển sang tab Application (Ứng dụng).\\n5. Nhìn bên trái mục Storage (Bộ nhớ) -> Cookies -> chọn tiktok.com\\n6. Tìm hàng có chữ sessionid ở cột Name.\\n7. Copy dòng mã ở cột Value và dán vào ô Tiktok SessionID."
        QMessageBox.information(self, "Hướng dẫn lấy mã Tiktok", msg)
"""
    content = content.replace('def _save(self) -> None:', guide_logic + '\n    def _save(self) -> None:')

with open('tab_settings.py', 'w', encoding='utf-8') as f:
    f.write(content)

import shutil
try:
    shutil.copy('voice_profiles.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\voice_profiles.py')
    shutil.copy('ui.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\ui.py')
    shutil.copy('tab_settings.py', r'dist\VEO_4.0_V2.2.6_PROMAX\_internal\tab_settings.py')
except Exception:
    pass

print("Patched UI and voices successfully!")
