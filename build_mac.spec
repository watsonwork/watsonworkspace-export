# -*- mode: python -*-

import os

working_dir = os.getcwd()

block_cipher = None

single_file = True

a = Analysis(['wwexport/__main__.py'],
             binaries=[],
             datas=[
                    (working_dir + '/wwexport/resources/styles.css','wwexport/resources'),
                    (working_dir + '/wwexport/templates/messages.html','wwexport/templates'),
                   ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

if single_file:
    exe = EXE(pyz,
              a.scripts,
              a.binaries,
              a.zipfiles,
              a.datas,
              [],
              name='IBM Watson Workspace Export Utility',
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              runtime_tmpdir=None,
              console=True,
              icon='resources/icon.icns',
              info_plist={
                  'CFBundlePackageType': 'APPL'
              },)
else:
    exe = EXE(pyz,
              a.scripts,
              [],
              exclude_binaries=True,
              name='IBM Watson Workspace Export Utility',
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              console=True,
              icon='resources/icon.icns')
    coll = COLLECT(exe,
              a.binaries,
              a.zipfiles,
              a.datas,
              strip=False,
              upx=True,
              name='wwexporttool')
