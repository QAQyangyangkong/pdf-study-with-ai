# Build on Windows with: python -m PyInstaller --noconfirm packaging/StudyDesk.spec
from pathlib import Path

project = Path(SPECPATH).parent
analysis = Analysis(
    [str(project / 'launcher.py')],
    pathex=[str(project / 'src')], binaries=[], datas=[], hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='StudyDesk',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
collection = COLLECT(exe, analysis.binaries, analysis.datas, strip=False,
                     upx=False, name='StudyDesk')
