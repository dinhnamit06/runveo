@echo off
echo [*] Dang nang cap PyArmor len ban moi nhat...
pip install --upgrade pyarmor -q

echo [*] Dang ma hoa ma nguon...
if exist "dist_obfuscated" rd /s /q "dist_obfuscated"

:: Lenh chuan cho PyArmor 8.x: 
:: pyarmor gen -O [output] -r [input]
pyarmor gen -O dist_obfuscated -r . --exclude "build,dist,venv,data_general,icons,obfuscate.bat,bao_mat_code.bat,build_exe.py,build_obfuscated_exe.py"

if %ERRORLEVEL% EQU 0 (
    echo [OK] Ma hoa thanh cong! Code da duoc bao ve trong thu muc 'dist_obfuscated'.
    echo [*] Gio ban hay chay: python build_obfuscated_exe.py
) else (
    echo [!] Loi trong qua trinh ma hoa. Vui long kiem tra version pyarmor (pyarmor --version).
)
pause
