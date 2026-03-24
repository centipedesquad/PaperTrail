# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# Collect all local modules
datas = []
hiddenimports = ['PySide6', 'arxiv']

# Add all local Python packages as datas
import os
src_dir = os.path.dirname(os.path.abspath(SPEC))

# Collect all .py files from local modules
for root, dirs, files in os.walk(src_dir):
    # Skip build, dist, __pycache__ directories
    dirs[:] = [d for d in dirs if d not in ['build', 'dist', '__pycache__', '.venv', '.git']]

    for file in files:
        if file.endswith('.py'):
            full_path = os.path.join(root, file)
            # Get relative path from src_dir
            rel_path = os.path.relpath(full_path, src_dir)
            # Skip main.py as it's the entry point
            if rel_path != 'main.py':
                # Add as data file, preserving directory structure
                dest_dir = os.path.dirname(rel_path) if os.path.dirname(rel_path) else '.'
                datas.append((full_path, dest_dir))

# Also add migration SQL files
for root, dirs, files in os.walk(os.path.join(src_dir, 'database', 'migrations')):
    for file in files:
        if file.endswith('.sql'):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, src_dir)
            dest_dir = os.path.dirname(rel_path)
            datas.append((full_path, dest_dir))

a = Analysis(
    ['main.py'],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PaperTrail',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PaperTrail',
)

app = BUNDLE(
    coll,
    name='PaperTrail.app',
    icon=os.path.join(src_dir, 'assets', 'AppIcon.icns'),
    bundle_identifier=None,
)
