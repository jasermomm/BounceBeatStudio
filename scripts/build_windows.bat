@echo off
call "%~dp0..\BUILD_WINDOWS_EXE.bat" %*
exit /b %ERRORLEVEL%
