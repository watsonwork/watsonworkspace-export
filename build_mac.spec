# -*- mode: python -*-

block_cipher = None


a = Analysis(['wwexport/__main__.py'],
             binaries=[],
             datas=[],
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
          console=True , icon='wwexport/resources/icon.icns')

# work in progress - needs a GUI
#app = BUNDLE(exe,
#             name='IBM Watson Workspace Export Utility.app',
#             icon='wwexport/resources/icon.icns',
#             bundle_identifier='com.ibm.workspace.export')
