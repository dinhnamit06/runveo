import sys

with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace QLineEdit with QComboBox for voicebox_id
init_target = """        self.voicebox_id = QLineEdit()
        self.voicebox_id.setPlaceholderText("Nhập Voice ID từ giao diện Voicebox (chỉ dùng cho Voicebox)")
        self.voicebox_id.setText(str(getattr(self._cfg, "idea_voicebox_id", "") if self._cfg is not None else ""))
        vb_layout.addWidget(self.voicebox_id)"""

init_patch = """        self.voicebox_id = QComboBox()
        self.voicebox_id.setEditable(True)
        self.voicebox_id.setMinimumWidth(180)
        
        self.btn_refresh_vb = QPushButton("Lấy danh sách giọng")
        self.btn_refresh_vb.setFixedWidth(130)
        self.btn_refresh_vb.clicked.connect(self._fetch_voicebox_voices)
        
        saved_id = str(getattr(self._cfg, "idea_voicebox_id", "") if self._cfg is not None else "")
        if saved_id:
            self.voicebox_id.addItem(saved_id, saved_id)
            self.voicebox_id.setCurrentText(saved_id)
            
        vb_layout.addWidget(self.voicebox_id, 1)
        vb_layout.addWidget(self.btn_refresh_vb)"""

if init_target in content:
    content = content.replace(init_target, init_patch)

# Update get_settings for voicebox_id (ComboBox text)
set_target = """            "voicebox_id": self.voicebox_id.text().strip(),"""
set_patch = """            "voicebox_id": self.voicebox_id.currentText().strip(),"""

if set_target in content:
    content = content.replace(set_target, set_patch)

# Update _persist_config for voicebox_id
per_target = """            setattr(self._cfg, "idea_voicebox_id", self.voicebox_id.text().strip())"""
per_patch = """            setattr(self._cfg, "idea_voicebox_id", self.voicebox_id.currentText().strip())"""

if per_target in content:
    content = content.replace(per_target, per_patch)

# Update _preview_tts_voice
prev_target = """        voice_key = str(self.voicebox_id.text() or "").strip() if provider == "voicebox" else str(self.voice_profile.currentData() or "").strip()"""
prev_patch = """        voice_key = str(self.voicebox_id.currentText() or "").strip() if provider == "voicebox" else str(self.voice_profile.currentData() or "").strip()"""

if prev_target in content:
    content = content.replace(prev_target, prev_patch)

# Add event connection patch (since it was editingFinished before)
conn_target = """            self.voicebox_id.editingFinished.connect(self._persist_config)"""
conn_patch = """            self.voicebox_id.currentTextChanged.connect(lambda _=None: self._persist_config())"""

if conn_target in content:
    content = content.replace(conn_target, conn_patch)

# Add _fetch_voicebox_voices method
fetch_method = """
    def _fetch_voicebox_voices(self) -> None:
        import urllib.request
        import json
        self.btn_refresh_vb.setText("Đang lấy...")
        self.btn_refresh_vb.setEnabled(False)
        QApplication.processEvents()
        
        found_voices = []
        ports = [17493, 8000]
        endpoints = ['/v1/voices', '/api/voices', '/voices', '/v1/models']
        
        for port in ports:
            for ep in endpoints:
                try:
                    url = f"http://127.0.0.1:{port}{ep}"
                    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        # Parse various standard formats
                        items = []
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict) and 'data' in data:
                            items = data['data']
                        elif isinstance(data, dict) and 'voices' in data:
                            items = data['voices']
                            
                        for item in items:
                            if isinstance(item, dict):
                                v_id = item.get('id') or item.get('voice_id') or item.get('name')
                                v_name = item.get('name') or item.get('id') or v_id
                                if v_id:
                                    found_voices.append((str(v_name), str(v_id)))
                        if found_voices:
                            break
                except Exception:
                    pass
            if found_voices:
                break
                
        self.btn_refresh_vb.setText("Lấy danh sách giọng")
        self.btn_refresh_vb.setEnabled(True)
        
        if found_voices:
            self.voicebox_id.clear()
            for name, vid in found_voices:
                self.voicebox_id.addItem(name, vid)
            QMessageBox.information(self, "Thành công", f"Đã lấy được {len(found_voices)} giọng từ Voicebox!")
        else:
            QMessageBox.warning(self, "Lỗi kết nối", "Không lấy được danh sách giọng. Hãy chắc chắn Voicebox đang chạy.\\nBạn vẫn có thể gõ tên/ID giọng thủ công vào ô.")

"""

if "_fetch_voicebox_voices" not in content:
    content = content.replace("    def _preview_tts_voice", fetch_method + "    def _preview_tts_voice")


with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched tab_idea_to_video.py for Voicebox auto-fetch")
