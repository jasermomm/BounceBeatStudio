from pathlib import Path


def test_windows_builder_version_lookup_is_safe_for_paths_with_spaces():
    root = Path(__file__).resolve().parents[1]
    script = (root / "BUILD_WINDOWS_EXE.bat").read_text(encoding="utf-8")
    assert 'set "VERSION_FILE=%TEMP%\\bouncebeat-version-' in script
    assert '"%VENV_PY%" -c "import bouncebeat; print(bouncebeat.__version__)" > "%VERSION_FILE%"' in script
    assert 'set /p "APP_VERSION="<"%VERSION_FILE%"' in script
    assert not any("for /f" in line.lower() and "%VENV_PY%" in line for line in script.splitlines())
