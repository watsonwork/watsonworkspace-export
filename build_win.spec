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
                                       stderr=subprocess.STDOUT,
                                       cwd=working_dir,
                                       env=os.environ)
  if git_hash_process.returncode is None or 0:
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
                                       cwd=working_dir,
                                       env=os.environ)
  git_status,_ = git_status_process.communicate()
  git_uncommitted = len(git_status.decode("UTF-8").rstrip("\n\r")) > 0
  print("Git uncommitted changes {}".format(git_uncommitted))
  if git_uncommitted:
      git_hash = git_hash + "+"

  build_info = "win {} - {}".format(datetime.datetime.now(), git_hash)

except FileNotFoundError as e:
  print("FileNotFound on subprocess attempting to get commit info from git - do you have git installed and is this a git repo?")
  raise RuntimeError("error getting git hash for build info - git not installed?")

print("Using build info {}".format(build_info))

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
          name='IBM Watson Workspace Export Utility for Windows',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon='resources/icon.ico')
#coll = COLLECT(exe,
#               a.binaries,
#               a.zipfiles,
#               a.datas,
#               strip=False,
#               upx=True,
#               name='__main__')
