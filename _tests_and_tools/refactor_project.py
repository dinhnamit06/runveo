import os
import shutil
import re
from pathlib import Path

# Mapping of file names (without .py) to their new package paths
MODULE_MAPPING = {
    # Core
    "main": "src.core",
    "run_veo_4.0": "src.core",
    "UI_main": "src.core",
    "settings_manager": "src.core",
    "branding_config": "src.core",
    "License": "src.core",
    
    # UI
    "ui": "src.ui",
    "login": "src.ui",
    "status_panel": "src.ui",
    "status_help_view": "src.ui",
    "style": "src.ui",
    "popup_theme": "src.ui",
    "tab_character_sync": "src.ui",
    "tab_copy_video": "src.ui",
    "tab_create_image": "src.ui",
    "tab_grok_settings": "src.ui",
    "tab_idea_to_video": "src.ui",
    "tab_image_to_video": "src.ui",
    "tab_settings": "src.ui",
    "tab_text_to_video": "src.ui",
    
    # API
    "API_Create_image": "src.api",
    "API_image_to_image": "src.api",
    "API_image_to_video": "src.api",
    "API_sync_chactacter": "src.api",
    "API_text_to_video": "src.api",
    "SORA_API_UPLOAD_IMAGE": "src.api",
    "grok_api_image_to_video": "src.api",
    "grok_api_text_to_video": "src.api",
    "chrome": "src.api",
    "chrome_process_manager": "src.api",
    "grok_chrome_manager": "src.api",
    
    # Workflows
    "A_workflow_generate_image": "src.workflows",
    "A_workflow_get_token": "src.workflows",
    "A_workflow_image_to_image": "src.workflows",
    "A_workflow_image_to_video": "src.workflows",
    "A_workflow_sync_chactacter": "src.workflows",
    "A_workflow_text_to_video": "src.workflows",
    "grok_workflow_create_image_ui": "src.workflows",
    "grok_workflow_image_to_video": "src.workflows",
    "grok_workflow_text_to_video": "src.workflows",
    "worker_run_workflow": "src.workflows",
    "worker_run_workflow_grok": "src.workflows",
    "workflow_run_control": "src.workflows",
    
    # Features
    "idea_to_video": "src.features",
    "gemini_automation": "src.features",
    "storytelling_exporter": "src.features",
    "tiktok_tts_exporter": "src.features",
    "merge+video": "src.features",
    
    # Utils
    "tts_voices": "src.utils",
    "voice_profiles": "src.utils",
    "content_source": "src.utils",
}

def create_structure_and_move():
    base_dir = Path(".")
    src_dir = base_dir / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "__init__.py").touch()
    
    moved_files = []
    
    for module_name, target_pkg in MODULE_MAPPING.items():
        pkg_path = base_dir / target_pkg.replace(".", "/")
        pkg_path.mkdir(parents=True, exist_ok=True)
        (pkg_path / "__init__.py").touch()
        
        file_name = f"{module_name}.py"
        src_file = base_dir / file_name
        
        # Special handling for run_veo_4.0.py
        if module_name == "run_veo_4.0":
            dest_file = pkg_path / "run_veo_4_0.py"
        else:
            dest_file = pkg_path / file_name
            
        if src_file.exists():
            shutil.move(str(src_file), str(dest_file))
            moved_files.append(dest_file)
            print(f"Moved {file_name} -> {dest_file}")
            
    root_init = base_dir / "__init__.py"
    if root_init.exists():
        root_init.unlink()
        
    return moved_files

def refactor_imports():
    sorted_modules = sorted(MODULE_MAPPING.keys(), key=len, reverse=True)
    
    for py_file in Path("src").rglob("*.py"):
        if not py_file.is_file(): continue
        
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Could not read {py_file}: {e}")
            continue
            
        new_content = content
        
        for mod in sorted_modules:
            pkg = MODULE_MAPPING[mod]
            
            # Pattern 1: import module -> from pkg import module
            # Using \b to ensure word boundary.
            pattern1 = re.compile(rf'^([ \t]*)import\s+{re.escape(mod)}\b', re.MULTILINE)
            new_content = pattern1.sub(rf'\1from {pkg} import {mod}', new_content)
            
            # Pattern 1b: import module as alias -> from pkg import module as alias
            pattern1b = re.compile(rf'^([ \t]*)import\s+{re.escape(mod)}\s+as\s+(\w+)', re.MULTILINE)
            new_content = pattern1b.sub(rf'\1from {pkg} import {mod} as \2', new_content)
            
            # Pattern 2: from module import X -> from pkg.module import X
            pattern2 = re.compile(rf'^([ \t]*)from\s+{re.escape(mod)}\s+import\b', re.MULTILINE)
            new_content = pattern2.sub(rf'\1from {pkg}.{mod} import', new_content)
            
        if new_content != content:
            with open(py_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Refactored imports in {py_file}")

if __name__ == "__main__":
    print("Starting refactoring...")
    create_structure_and_move()
    print("Files moved. Refactoring imports...")
    refactor_imports()
    
    print("Creating stub runner...")
    with open("run_veo_4.0.py", "w", encoding="utf-8") as f:
        f.write("import sys\nimport os\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\nimport src.core.run_veo_4_0\n")
    print("Refactoring complete.")
