# Watson Workspace Export Utility

This repository contains a Python project to export the contents of Watson Workspace for a given user.

The included script will find all your spaces, then iterate over each one to
- create an appropriate folder structure in your home directory
- export a csv file with information about members of the space
- iterate over messages, starting with the oldest, and printing all to CSVs, organized into folders by year and given a name `messages [month].csv`

This can be a very long running process, and currently, it is possible for a JWT token to expire partially through the export.

Due to the possible expiration of the JWT auth token, and potential for other issues or network disruptions during such a long running process, the export was made resumable. If the tool detects messages already exported for a space, it will attempt to find the most recently message and will continue from that point. This feature is also useful if you want to export a space, and then later on rerun the export to get new messages since your last export. In this case, the tool can be used to incrementally export a space, though it will not consider message edits or deletions.

There are two main options for executing the utility:
1. Running as a script
2. Running from a built executable

## Setup

Setup is required for
- Running as a script
- Building

Setup is NOT required For
- Running from a built executable

To setup the environment

1. Make sure you have Python 3.x installed (check with `python --version`). Note: this package was developed with python 3.7.

2. It is highly recommended that you install required packages into a Python virtual environment. For instance, before running the setup, you can create and activate a virtual environment for the project with:

  - MacOS
  ```
  python -m venv env
  source env/bin/activate
  ```
  - Windows
  ```
  python -m venv env
  env\Scripts\activate.bat
  ```
  This will create a directory called `env` in your working directory (normally in the project) and activate it for the current terminal session.


3. Install required packages. Note that this step will download and install additional packages to your machine which have their own licenses attached. There are many ways to do this, but the most simple may be to run `pip install -r requirements.txt` from the project directory after activating your virtual environment (you may need to use `pip3` instead of `pip` depending on your environment). A Pipfile is also provided if you choose to use pipenv commands.

See https://docs.python.org/3/tutorial/venv.html or https://pipenv.readthedocs.io/en/latest/ for more information and approaches to virtual environments for Python.

## Running as a script

Running as a script does not require a build, but does require the setup steps be completed.

### As a user

1. Obtain your JWT from Workspace by visiting https://workspace.ibm.com/exporttoken
2. Change to the directory containing this project
3. Run `python -m wwexport --jwt=WATSON_WORK_JWT`, replacing WATSON_WORK_JWT with the value you copied from the export token page above

### As an app

1. Obtain an app ID and secret from https://developer.watsonwork.ibm.com/apps
2. Add the app to spaces to be exported
3. Change to the directory containing this project
4. Run `python -m wwexport --appcred APP_ID:APP_SECRET --spaceid SPACE_TO_EXPORT`

Run `python -m wwexport -h` for more options, including options on exporting files.

## Building

The build process uses [PyInstaller](http://www.pyinstaller.org/) to freeze the code into a single executable with the necessary dependencies.

1. Follow the steps for setup above.
2. Change to the directory containing this project
3. Run `pyinstaller --clean build_mac.spec` or `pyinstaller --clean build_win.spec` depending on your platform. This will create directories called `build` and `dist` in your project, and your built executable will be at `dist/IBM Watson Workspace Export Utility` on Mac and `dist/IBM Watson Workspace Export Utility.exe` on Windows. You may be asked to confirm partially through the process if you use the `--clean` option.

The `build_mac.spec` and `build_win.spec` are customized versions of the base spec files which can be generated automatically by PyInstaller.

Note that you can only build for the environment you build on. In other words, in order to build a Mac executable, you must run the build on MacOS. In order to build for Windows, you must run the build on Windows.

## Running from a built executable

Instead of executing `python -m wwexport` followed by options, you will execute using the standalone executable. All the options you may pass remain the same.

- Windows

  1. Obtain your JWT from Workspace by visiting https://workspace.ibm.com/exporttoken
  2. Launch (double click on) the `IBM Watson Workspace Export Utility.exe` file or run it from the terminal
  3. Paste or input your auth token from step 1 when prompted for a JWT

- Mac

  1. Obtain your JWT from Workspace by visiting https://workspace.ibm.com/exporttoken
  2. Open a terminal and change to the directory containing your built executable
  3. Run `"./IBM Watson Workspace Export Utility" --jwt=WATSON_WORK_JWT`, replacing WATSON_WORK_JWT with the value you copied from the export token page above

Why is Mac a bit more tricky than Windows? The length of the auth token exceeds the length allowed for a prompt in the terminal, so the utility may not prompt for it. It must be passed to the utility directly.

## Exported Metadata

When files are exported, additional metadata files are created to save information about file creators, dates, and the relationship of file IDs to paths on the local file system. This aids when resuming an export since the tool uses the metadata files to skips downloads of files already downloaded. Unless IDs were used as file names (which is not very user friendly), it is otherwise not possible to know which files were downloaded without meta files, since multiple files can have the same name in a space. These meta files are also helpful in knowing information on the message associated with a file, or finding the file corresponding to a message.

# LICENSE

See the [LICENSE](LICENSE) file. Earlier versions of this project were released under Apache 2.0.
