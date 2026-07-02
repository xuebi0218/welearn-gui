# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('src/donate_qr.jpg', 'src/'), ('src/help_1.jpg', 'src/'), ('src/help_2.jpg', 'src/'), ('src/help_3.jpg', 'src/'), ('src/nobi.png', 'src/')]
datas += collect_data_files('customtkinter')


a = Analysis(
    ['src\\welearn_gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['queue', 'PIL', 'PIL.Image'],
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
    a.binaries,
    a.datas,
    [],
    name='WelearnGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
