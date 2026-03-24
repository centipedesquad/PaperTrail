"""
Setup script for building PaperTrail macOS application bundle.
"""

from setuptools import setup

APP = ['src/main.py']
DATA_FILES = [
    ('', ['README.md']),
]
OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'PySide6',
        'arxiv',
        'requests',
        'dateutil',
        'fitz',  # PyMuPDF
        'sqlite3',
    ],
    'includes': [
        'database',
        'models',
        'api',
        'services',
        'ui',
        'utils',
    ],
    'excludes': [
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
    ],
    'iconfile': 'src/assets/AppIcon.icns',
    'plist': {
        'CFBundleName': 'PaperTrail',
        'CFBundleDisplayName': 'PaperTrail',
        'CFBundleIdentifier': 'com.papertrail.app',
        'CFBundleVersion': '0.2.0',
        'CFBundleShortVersionString': '0.2.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'PDF Document',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['com.adobe.pdf'],
            }
        ],
    },
    'arch': 'universal2',  # Support both Intel and Apple Silicon
}

setup(
    name='PaperTrail',
    version='0.2.0',
    description='arXiv Paper Management Application',
    author='PaperTrail',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
