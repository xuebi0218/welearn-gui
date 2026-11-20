# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('src/donate_qr.jpg', 'src/'), ('src/help_1.jpg', 'src/'), ('src/help_2.jpg', 'src/'), ('src/help_3.jpg', 'src/'), ('src/mascot.png', 'src/'), ('src/mascot_classic.png', 'src/'), ('src/strip.png', 'src/'), ('src/banner.png', 'src/'), ('src/anim_0.png', 'src/'), ('src/anim_1.png', 'src/'), ('src/anim_2.png', 'src/'), ('src/anim_3.png', 'src/'), ('src/anim_4.png', 'src/'), ('src/anim_5.png', 'src/')]
datas += collect_data_files('customtkinter')


a = Analysis(
    ['src\\welearn_gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['queue', 'PIL', 'PIL.Image', 'brotli'],
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
