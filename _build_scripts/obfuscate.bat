@echo off
echo [*] Dang ma hoa ma nguon voi PyArmor...
pip install pyarmor -q

:: Xoa cac thu muc cu neu co
if exist "dist_obfuscated" rd /s /q "dist_obfuscated"

:: Ma hoa toan bo thu muc hien tai
:: -e: ma hoa moi file rieng biet
:: -r: de quy vao cac thu muc con
:: -O: Thu muc dau ra (VIET HOA)
pyarmor gen -r -e . --exclude "build,dist,venv,data_general,icons,obfuscate.bat,build_exe.py,build_obfuscated_exe.py" -O dist_obfuscated

if %ERRORLEVEL% EQU 0 (
    echo [OK] Ma hoa thanh cong! Code da duoc bao ve trong thu muc 'dist_obfuscated'.
    echo [*] Gio ban hay chay: python build_obfuscated_exe.py
) else (
    echo [!] Loi trong qua trinh ma hoa.
)
pause
