# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run_app.py'],  # This has been updated to use the wrapper script
    pathex=['C:\\Users\\Useless\\Desktop\\final erp'],
    binaries=[],
    datas=[
        ('logo.ico', '.'),
        ('logo_base64.txt', '.'),
        ('secrets.toml', '.'),
        ('style.css', '.'),
        ('temp_watermark_logo.png', '.'),
        ('assets', 'assets'),
        ('attachments', 'attachments'),
        ('components', 'components'),
        ('modules', 'modules'),
        ('.streamlit', '.streamlit'),
    ],
    hiddenimports=[
        'streamlit',
        'streamlit.web',
        'streamlit.web.cli',
    ],
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
    name='Pharmacy Management System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Pharmacy Management System',
)