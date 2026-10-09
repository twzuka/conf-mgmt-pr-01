@echo off
setlocal
set "PROJECT_DIR=%~dp0.."
python "%PROJECT_DIR%\src\main.py" ^
    --vfs-path "%PROJECT_DIR%\vfs\demo.xml" ^
    --prompt "stage4> " --script "%~dp0stage4.txt"
