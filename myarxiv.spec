# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for myArXiv macOS application.
"""

import sys
from pathlib import Path

block_cipher = None

# Get the source directory
src_dir = Path('src').absolute()

a = Analysis(
    ['src/main.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        ('src/database/migrations/*.sql', 'database/migrations'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'arxiv',
        'requests',
        'dateutil',
        'fitz',  # PyMuPDF
        'sqlite3',
        'database',
        'database.connection',
        'database.repositories',
        'database.migration_manager',
        'models',
        'api',
        'api.arxiv_client',
        'services',
        'services.config_service',
        'services.paper_service',
        'services.fetch_service',
        'services.pdf_service',
        'ui',
        'ui.main_window',
        'ui.widgets',
        'ui.widgets.paper_cell_widget',
        'ui.widgets.paper_feed_widget',
        'ui.widgets.rating_widget',
        'ui.widgets.note_editor_widget',
        'ui.dialogs',
        'ui.dialogs.fetch_papers_dialog',
        'ui.dialogs.pdf_action_dialog',
        'utils',
        'utils.platform_utils',
        'utils.async_utils',
        'utils.filename_utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
        'pytest',
        'black',
        'flake8',
        'mypy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='myArXiv',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='myArXiv',
)

app = BUNDLE(
    coll,
    name='myArXiv.app',
    icon=None,  # Add icon later
    bundle_identifier='com.myarxiv.app',
    version='0.2.0',
    info_plist={
        'CFBundleName': 'myArXiv',
        'CFBundleDisplayName': 'myArXiv',
        'CFBundleVersion': '0.2.0',
        'CFBundleShortVersionString': '0.2.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
    },
)
