# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the unified `coverity-metrics` binary.
# Run from the repo root:  pyinstaller packaging/coverity-metrics.spec --clean --noconfirm

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# SPECPATH is injected by PyInstaller and points to this spec file's dir.
REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

# Bundle templates + CSS at the same relative path the source expects, so
# `os.path.dirname(__file__)/templates` (dashboard.py) resolves inside _MEIPASS
# without any code changes.
datas = [
    (os.path.join(REPO_ROOT, 'coverity_metrics', 'templates'), 'coverity_metrics/templates'),
    (os.path.join(REPO_ROOT, 'coverity_metrics', 'static'),    'coverity_metrics/static'),
]

# Hidden imports PyInstaller's static analysis tends to miss.
hiddenimports = [
    'jinja2.ext',
]
# __main__.py dispatches via importlib.import_module(); pull every subpackage in.
hiddenimports += collect_submodules('coverity_metrics')
hiddenimports += collect_submodules('plotly')
hiddenimports += collect_submodules('pg8000')

# Trim GUI toolkits + notebook stack we never use (~40 MB savings).
# matplotlib / PIL / seaborn / openpyxl are also excluded — pandas / plotly
# will optionally import them if installed, but this project never renders
# PNGs or writes .xlsx. Excluding here keeps the binary lean even if the
# build venv accidentally pulls them in as transitives.
# sqlite3 / _sqlite3: pandas.io.sql transitively imports stdlib sqlite3 →
# _sqlite3.pyd + sqlite3.dll get bundled. We never call pd.read_sql /
# pd.to_sql, so exclude both to drop the sqlite3.dll BDBA finding.
# (pandas.io.sql itself must stay — pandas.io.api hard-imports it.)
# xml.parsers.expat / _elementtree: pandas.io.xml transitively imports the
# stdlib xml stack → pyexpat.pyd + _elementtree.pyd get bundled. We never
# call pd.read_xml / DataFrame.to_xml, so exclude the C extensions to drop
# the pyexpat.pyd BDBA finding (pandas.io.xml itself stays for the same
# reason as pandas.io.sql).
excludes = [
    'tkinter',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'IPython', 'jupyter', 'notebook', 'ipykernel', 'ipywidgets',
    'pytest', 'pytest_cov',
    'matplotlib', 'PIL', 'seaborn', 'openpyxl',
    'sqlite3', '_sqlite3',
    'pyexpat', '_elementtree',
]

a = Analysis(
    [os.path.join(SPECPATH, 'entry_point.py')],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='coverity-metrics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX triggers Windows Defender false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
