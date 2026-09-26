@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
set "APP=%PROJECT_DIR%\src\main.py"
set "STARTUP=%~dp0startup.txt"

echo === --vfs-path ===
echo exit | python "%APP%" --vfs-path "%PROJECT_DIR%\vfs.xml"

echo === --prompt ===
echo exit | python "%APP%" --prompt "demo> "

echo === --script ===
python "%APP%" --script "%STARTUP%"

echo === all parameters ===
python "%APP%" --vfs-path "%PROJECT_DIR%\vfs.xml" ^
    --prompt "demo> " --script "%STARTUP%"
