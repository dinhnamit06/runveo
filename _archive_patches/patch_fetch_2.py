import sys

with open('tab_idea_to_video.py', 'r', encoding='utf-8') as f:
    content = f.read()

fetch_method = '''
    def _fetch_voicebox_voices(self) -> None:
        import urllib.request
        import json
        from PyQt6.QtWidgets import QMessageBox, QApplication
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
            QMessageBox.warning(self, "Lỗi kết nối", "Không lấy được danh sách giọng. Hãy chắc chắn Voicebox đang chạy.\\nBạn vẫn có thể gõ tên/ID giọng thủ công vào ô thả xuống.")
'''

if 'def _fetch_voicebox_voices' not in content:
    content = content.replace('    def _preview_tts_voice(self) -> None:', fetch_method + '\n    def _preview_tts_voice(self) -> None:')

with open('tab_idea_to_video.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed!')
