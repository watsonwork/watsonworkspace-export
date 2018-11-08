# Watson Workspace Export Utility

This repository contains a Python project to export the contents of Watson Workspace for a given user.

The included script will find all your spaces, then iterate over each one to
- create an appropriate folder structure in your home directory
- export a csv file with information about members of the space
- iterate over messages, starting with the oldest, and printing all to CSVs, organized into folders by year and given a name `messages [month].csv`

This can be a very long running process, and currently, it is possible for a JWT token to expire partially through the export.

Due to the possible expiration of the JWT auth token, and potential for other issues or network disruptions during such a long running process, the export was made resumable. If the tool detects messages already exported for a space, it will attempt to find the most recently message and will continue from that point. This feature is also useful if you want to export a space, and then later on rerun the export to get new messages since your last export. In this case, the tool can be used to incrementally export a space, though it will not consider message edits or deletions.

## Running

1. Make sure you have Python 3.x installed (check with `python --version`)
2. Change to the directory containing this project
3. Run `python wwexport --jwt=WATSON_WORK_JWT`

Run `python wwexport -h` for more options, including options on exporting files.

When files are exported, additional metadata files are created to save information about file creators, dates, and the relationship of file IDs to paths on the local file system. This aids when resuming an export since the tool uses the metadata files to skips downloads of files already downloaded. Unless IDs were used as file names (which is not very user friendly), it is otherwise not possible to know which files were downloaded without meta files, since multiple files can have the same name in a space. These meta files are also helpful in knowing information on the message associated with a file, or finding the file corresponding to a message.

## Unfinished

- Accept a refresh token to refresh the JWT
- Add support for topics
- Add an optional flag to export annotations
- Make the resume tolerant of space name changes
- Update the members so multiple runs don't leave a lot of members files
- Enhance message export so message rows include lists of local file paths, not just the file IDs embedded in the message, to make finding local exported files from messages easier.
