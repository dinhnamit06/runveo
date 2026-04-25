import os
import subprocess
import sys
import io
import importlib.util
from pathlib import Path

# Force UTF-8 encoding for stdout to handle special characters in paths
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def build():
    # Change to project root directory
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    print(f"Building from: {project_root}")

    # Ensure necessary folders exist for bundling
    # Even if empty, we need them for the --add-data flag to not fail
    for folder in ["icons", "data_general", "Workflows"]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"Created placeholder folder: {folder}")

    # CLEAN BUILD: Remove old folders to avoid stale cache issues
    import shutil
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            print(f"Cleaning existing {folder} folder...")
            shutil.rmtree(folder, ignore_errors=True)

    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "VEO_4.0_V2.2.6_PROMAX",
        # Use existing icon if available
        "--icon", "icons/app_icon.ico" if os.path.exists("icons/app_icon.ico") else "NONE",
        # Data files
        "--add-data", "icons;icons",
        "--add-data", "data_general;data_general",
        "--add-data", "Workflows;Workflows",
        "--add-data", "qt_ui;qt_ui",
# Bundling all root .py files as data to resolve ModuleNotFoundError
        "--add-data", "*.py;.",
        # Explicit submodules for cloud/browser libraries
        "--collect-all", "google",
        "--collect-all", "playwright",
        # Hidden imports for safety
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "branding_config",
        "--hidden-import", "License",
# Explicitly include all workflow modules if they are imported dynamically
        "--hidden-import", "grok_api_text_to_video",
        "--hidden-import", "grok_api_image_to_video",
        "--hidden-import", "grok_workflow_text_to_video",
        "--hidden-import", "grok_workflow_image_to_video",
        # Search paths
        "--paths", ".",
        # The entry point script
        "run_veo_4.0.py"
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

    print("\n[BUILD] Executing PyInstaller command:")
    print(" ".join(cmd))
    
    try:
        subprocess.run(cmd, check=True)
        print("\n[SUCCESS] Build completed. Check the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed with exit code {e.returncode}")
        sys.exit(e.returncode)

if __name__ == "__main__":
    build()
