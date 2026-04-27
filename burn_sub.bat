REM --- For bilibili embedded subtitles ---
@echo off
chcp 65001 >nul
setlocal

REM --- Check if a folder was dragged onto this bat ---
if "%~1"=="" (
    echo Please drag a folder onto this bat file.
    pause
    exit /b 1
)

if not exist "%~1\" (
    echo "%~1" is not a folder.
    pause
    exit /b 1
)

set "FOLDER=%~1"
set "FOLDER_NAME=%~n1"
set "OUTPUT_DIR=%USERPROFILE%\Downloads"
set "OUTPUT=%OUTPUT_DIR%\%FOLDER_NAME%_sub.mp4"

REM --- Verify required files exist ---
if not exist "%FOLDER%\video.mp4" (
    echo [ERROR] video.mp4 not found in: %FOLDER%
    pause
    exit /b 1
)

if not exist "%FOLDER%\video.cht.srt" (
    echo [ERROR] video.cht.srt not found in: %FOLDER%
    pause
    exit /b 1
)

echo ========================================
echo Input folder : %FOLDER%
echo Output file  : %OUTPUT%
echo ========================================
echo.

REM --- cd into folder so ffmpeg subtitles filter sees plain filenames ---
pushd "%FOLDER%"

ffmpeg -i video.mp4 -vf "subtitles=video.cht.srt:force_style='Fontname=Microsoft JhengHei,Fontsize=22,Bold=1,Outline=1.5'" -c:a copy "%OUTPUT%" -y

set "EXITCODE=%ERRORLEVEL%"
popd

echo.
if "%EXITCODE%"=="0" (
    echo [OK] Done! Output: %OUTPUT%
) else (
    echo [FAIL] ffmpeg exited with code %EXITCODE%
)
pause
endlocal
