@echo off
setlocal
set "PROJECT_DIR=%~dp0.."
python "%PROJECT_DIR%\src\main.py" ^
    --vfs-path "%PROJECT_DIR%\vfs\demo.xml" ^
    --prompt "stage5> " --script "%~dp0stage5.txt"
