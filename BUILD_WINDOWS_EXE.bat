@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title BounceBeat Studio - Windows EXE Builder
color 0B
set "CLEAN_VENV=0"
set "SKIP_TESTS=0"
set "NO_PAUSE=0"
set "INSTALL_FLUIDSYNTH=0"
call :parse_args %*
call :banner
if not exist "pyproject.toml" (
    echo [ERROR] pyproject.toml was not found in the project root.
    goto :failed
)
if not exist "packaging\bouncebeat.spec" (
    echo [ERROR] packaging\bouncebeat.spec was not found.
    goto :failed
)
set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ERROR] Python was not found. Install 64-bit Python 3.11 or newer.
    goto :failed
)
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] BounceBeat Studio requires Python 3.11 or newer.
    goto :failed
)
for /f "delims=" %%V in ('%PYTHON_CMD% -c "import platform; print(platform.python_version() + ' ' + platform.architecture()[0])"') do set "PYTHON_VERSION=%%V"
echo [OK] Python !PYTHON_VERSION!
if "%CLEAN_VENV%"=="1" if exist ".venv" (
    echo [1/7] Removing .venv...
    rmdir /s /q ".venv"
    if exist ".venv" goto :venv_remove_failed
)
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
    if errorlevel 1 rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
    echo [1/7] Creating .venv...
    %PYTHON_CMD% -m venv ".venv"
    if errorlevel 1 goto :failed
) else (
    echo [1/7] Reusing .venv.
)
set "VENV_PY=%CD%\.venv\Scripts\python.exe"
set "PYINSTALLER=%CD%\.venv\Scripts\pyinstaller.exe"
echo.
echo [2/7] Updating packaging tools...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed
echo.
echo [3/7] Installing application, tests, and build tools...
"%VENV_PY%" -m pip install -e ".[build,dev]"
if errorlevel 1 goto :failed
if "%INSTALL_FLUIDSYNTH%"=="1" (
    "%VENV_PY%" -m pip install -e ".[fluidsynth]"
    if errorlevel 1 echo [WARNING] Optional pyfluidsynth installation failed.
)
"%VENV_PY%" -c "import PySide6, pymunk, mido, pretty_midi, numpy, soundfile; print('PySide6', PySide6.__version__, '| Pymunk', pymunk.version)"
if errorlevel 1 goto :failed
set "VERSION_FILE=%TEMP%\bouncebeat-version-%RANDOM%-%RANDOM%.txt"
"%VENV_PY%" -c "import bouncebeat; print(bouncebeat.__version__)" > "%VERSION_FILE%"
if errorlevel 1 goto :failed
set /p "APP_VERSION="<"%VERSION_FILE%"
del /q "%VERSION_FILE%" >nul 2>&1
if not defined APP_VERSION set "APP_VERSION=unknown"
"%VENV_PY%" -m compileall -q src tests scripts run.py
if errorlevel 1 goto :failed
echo.
if "%SKIP_TESTS%"=="1" (
    echo [4/7] Tests skipped.
) else (
    echo [4/7] Running tests...
    "%VENV_PY%" -m pytest
    if errorlevel 1 goto :failed
)
echo.
echo [5/7] Running strict release validation...
"%VENV_PY%" scripts\validate_release.py --require-native
if errorlevel 1 goto :failed
echo.
if exist "vendor\ffmpeg.exe" (
    echo [6/7] Bundled FFmpeg detected.
    if not exist "vendor\ffprobe.exe" echo [WARNING] vendor\ffprobe.exe is missing.
) else (
    echo [6/7] No bundled FFmpeg. The application will use PATH or Settings.
)
echo.
echo [7/7] Building Windows application...
if exist "build" rmdir /s /q "build"
if exist "dist\BounceBeat Studio" rmdir /s /q "dist\BounceBeat Studio"
if not exist "%PYINSTALLER%" goto :failed
"%PYINSTALLER%" --noconfirm --clean "packaging\bouncebeat.spec"
if errorlevel 1 goto :failed
set "APP_DIR=%CD%\dist\BounceBeat Studio"
set "EXE_PATH=%APP_DIR%\BounceBeat Studio.exe"
set "ZIP_PATH=%CD%\dist\BounceBeat-Studio-!APP_VERSION!-Windows.zip"
if not exist "%EXE_PATH%" goto :failed
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
set "BB_APP_DIR=%APP_DIR%"
set "BB_ZIP_PATH=%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path ($env:BB_APP_DIR + '\*') -DestinationPath $env:BB_ZIP_PATH -CompressionLevel Optimal -Force"
if errorlevel 1 echo [WARNING] Portable ZIP creation failed.
"%VENV_PY%" -m pip freeze > "dist\build-requirements.txt"
color 0A
echo.
echo ================================================================
echo BUILD SUCCESSFUL
echo ================================================================
echo Executable: %EXE_PATH%
if exist "%ZIP_PATH%" echo Portable ZIP: %ZIP_PATH%
echo Keep the executable with every file in its application folder.
start "" "%APP_DIR%"
if "%NO_PAUSE%"=="0" pause
exit /b 0

:parse_args
if "%~1"=="" exit /b 0
if /I "%~1"=="--clean-venv" set "CLEAN_VENV=1"
if /I "%~1"=="--skip-tests" set "SKIP_TESTS=1"
if /I "%~1"=="--no-pause" set "NO_PAUSE=1"
if /I "%~1"=="--install-fluidsynth" set "INSTALL_FLUIDSYNTH=1"
shift
goto :parse_args

:banner
echo ================================================================
echo BOUNCEBEAT STUDIO WINDOWS BUILDER
echo ================================================================
echo Options: --clean-venv --skip-tests --install-fluidsynth --no-pause
echo.
exit /b 0

:venv_remove_failed
echo [ERROR] Could not remove .venv. Close programs using it and retry.
goto :failed

:failed
color 0C
echo.
echo ================================================================
echo BUILD FAILED
echo ================================================================
echo No release was produced. Review the error above.
if "%NO_PAUSE%"=="0" pause
exit /b 1
