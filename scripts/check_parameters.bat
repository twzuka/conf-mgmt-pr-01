@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
set "APP=%PROJECT_DIR%\src\main.py"
set "STARTUP=%~dp0startup.txt"

echo === --vfs-path ===
echo exit | python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\minimal.xml"

echo === --prompt ===
echo exit | python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\files.xml" --prompt "demo> "

echo === --script ===
python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\nested.xml" --script "%STARTUP%"

echo === all parameters ===
python "%APP%" --vfs-path "%PROJECT_DIR%\vfs\minimal.xml" ^
    --prompt "demo> " --script "%STARTUP%"

