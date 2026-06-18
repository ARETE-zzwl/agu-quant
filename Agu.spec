# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_data_files, copy_metadata


datas = [
    ('web', 'web'),
    ('tradingagents', 'tradingagents'),
    ('cli', 'cli'),
    ('docs', 'docs'),
    ('.env.example', '.'),
]
if os.path.isdir('assets'):
    datas.append(('assets', 'assets'))
datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')

hiddenimports = [
    'plotly',
    'plotly.express',
    'plotly.graph_objects',
    'plotly.subplots',
    'streamlit.web.cli',
]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['setuptools', 'pkg_resources'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TradingAgents-Astock',
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
    name='TradingAgents-Astock',
)
