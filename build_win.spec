# -*- mode: python -*-

import os
import subprocess
import datetime

working_dir = os.getcwd()

block_cipher = None

# include the build date, a hash of the latest commit, and a flag (+) on the
# commit hash if this was built with uncommitted changes
try:
  git_hash_process = subprocess.Popen(["git", "log", "-1", "--format=%H"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
  git_hash,_ = git_hash_process.communicate()

  git_hash = git_hash.decode("UTF-8").rstrip("\n\r")
  print("Git commit hash {}".format(git_hash))

  git_status_process = subprocess.Popen(["git", "status", "-s"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
  git_status,_ = git_status_process.communicate()
  git_uncommitted = len(git_status.decode("UTF-8").rstrip("\n\r")) > 0
  print("Git uncommitted changes {}".format(git_uncommitted))
  if git_uncommitted:
      git_hash = git_hash + "+"

  build_info = "{} - {}".format(datetime.datetime.now(), git_hash)

except FileNotFoundError as e:
  print("FileNotFound on subprocess attempting to get commit info from git - do you have git installed and is this a git repo?")
  raise e

with open("build.txt", "w") as build_file:
    build_file.write(build_info)

a = Analysis(['wwexport\\__main__.py'],
             binaries=[],
             datas=[
                    (working_dir + '/wwexport/resources/styles.css','wwexport/resources'),
                    (working_dir + '/wwexport/templates/messages.html','wwexport/templates'),
                    (working_dir + '/build.txt','wwexport'),
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
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          # exclude_binaries=True, ## only if you use a collect step after this
          name='IBM Watson Workspace Export Utility',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon='resources/icon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='__main__')
