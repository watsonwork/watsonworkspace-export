# -*- mode: python -*-

import os
import subprocess
import datetime

from PyInstaller.utils.hooks import exec_statement

working_dir = os.getcwd()

block_cipher = None

single_file = True

cert_datas = exec_statement("""
    import ssl
    print(ssl.get_default_verify_paths().cafile)""").strip().split()
cert_datas = [(f, 'lib') for f in cert_datas]
print(cert_datas)

# include the build date, a hash of the latest commit, and a flag (+) on the
# commit hash if this was built with uncommitted changes
try:
  git_hash_process = subprocess.Popen(["git", "log", "-1", "--format=%H"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       cwd=working_dir)
  if git_hash_process.returncode is 0:
    git_hash,_ = git_hash_process.communicate()
    git_hash = git_hash.decode("UTF-8").rstrip("\n\r")
    print("Git commit hash {}".format(git_hash))
  else:
    response,_ = git_hash_process.communicate()
    print("Problem getting hash information from git - perhaps this is not a git repo? Please build from a git repo to have complete build information. {}".format(response.decode("UTF-8")))
    raise RuntimeError("error getting git hash for build info - not a git repo?")

  git_status_process = subprocess.Popen(["git", "status", "-s"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       cwd=working_dir)
  git_status,_ = git_status_process.communicate()
  git_uncommitted = len(git_status.decode("UTF-8").rstrip("\n\r")) > 0
  print("Git uncommitted changes {}".format(git_uncommitted))
  if git_uncommitted:
      git_hash = git_hash + "+"

  build_info = "mac {} - {}".format(datetime.datetime.now(), git_hash)

except FileNotFoundError as e:
  print("FileNotFound on subprocess attempting to get commit info from git - do you have git installed and is this a git repo?")
  raise RuntimeError("error getting git hash for build info - git not installed?")

print("Using build info {}".format(build_info))

with open("build.txt", "w") as build_file:
    build_file.write(build_info)

a = Analysis(['wwexport/__main__.py'],
             binaries=[],
             datas=[
                    (working_dir + '/wwexport/resources/styles.css','wwexport/resources'),
                    (working_dir + '/wwexport/templates/messages.html','wwexport/templates'),
                    (working_dir + '/build.txt','wwexport'),
                   ] + cert_datas,
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
              name='IBM Watson Workspace Export Utility for Mac',
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              runtime_tmpdir=None,
              console=True,
              icon='resources/icon.icns',
              # this doesn't seem to have an effect since the plist is only supported for app bundles
              info_plist={
                  'CFBundlePackageType': 'APPL'
              },)
else:
    exe = EXE(pyz,
              a.scripts,
              [],
              exclude_binaries=True,
              name='IBM Watson Workspace Export Utility for Mac',
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
