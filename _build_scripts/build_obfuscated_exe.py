import os
import subprocess
import sys
import io
import importlib.util
import shutil
from pathlib import Path

# Force UTF-8 encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def build_obfuscated():
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    
    obf_dir = project_root / "dist_obfuscated"
    
    if not obf_dir.exists():
        print("[ERROR] Khong tim thay thu muc 'dist_obfuscated'. Vui long chay 'obfuscate.bat' truoc!")
        return

    print(f"Building OBFUSCATED EXE from: {obf_dir}")

    # PyInstaller command for obfuscated code
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "VEO_4.0_V2.2.6_PROTECTED",
        "--icon", "icons/app_icon.ico" if os.path.exists("icons/app_icon.ico") else "NONE",
        
        # Paths to search for modules (Fix ModuleNotFoundError for obfuscated files)
        "--paths", str(obf_dir),

        # Add data from original folders
        "--add-data", "icons;icons",
        "--add-data", "data_general;data_general",
        "--add-data", "Workflows;Workflows",
        
        # Add the UI folder from original source (as it's not obfuscated in targeted strategy)
        "--add-data", "qt_ui;qt_ui",
        
        # Collector for dependencies
        "--collect-all", "google",
        "--collect-all", "playwright",
        
        # Hidden imports (Force include obfuscated modules)
        "--hidden-import", "branding_config",
        "--hidden-import", "License",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        
        # Entry point is the obfuscated script
        str(obf_dir / "run_veo_4.0.py")
    ]

    if importlib.util.find_spec("edge_tts") is not None:
        cmd.extend(["--collect-all", "edge_tts", "--hidden-import", "edge_tts"])
    else:
        print("[WARN] edge_tts is not installed; Edge TTS will not be bundled. Install with: pip install edge-tts")

    # Clean up command if icon is missing
    if "--icon" in cmd and "NONE" in cmd:
        icon_idx = cmd.index("--icon")
        cmd.pop(icon_idx + 1)
        cmd.pop(icon_idx)

    print("\n[BUILD] Executing Protected Build Command...")
    
    try:
        subprocess.run(cmd, check=True)
        print("\n" + "="*50)
        print("[SUCCESS] Build hoan tat!")
        print("EXE cua ban nam trong: dist/VEO_4.0_V2.2.6_PROTECTED")
        print("Code da duoc ma hoa chong decomplier boi PyArmor.")
        print("="*50)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build that bai: {e}")

if __name__ == "__main__":
    build_obfuscated()
