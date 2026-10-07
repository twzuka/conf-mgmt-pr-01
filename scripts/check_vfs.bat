@echo off
setlocal EnableDelayedExpansion
set "PROJECT_DIR=%~dp0.."
set "APP=%PROJECT_DIR%\src\main.py"

for %%N in (minimal files nested invalid invalid_base64 missing) do (
    echo === VFS: %%N ===
    python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\%%N.xml" --prompt "demo> " --script "%~dp0startup.txt"
    echo Exit code: !errorlevel!
)

echo === missing --vfs-path ===
python "%APP%"
echo Exit code: !errorlevel!

echo === missing startup script ===
echo exit | python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\minimal.xml" --script "%~dp0missing.txt"
echo Exit code: !errorlevel!
