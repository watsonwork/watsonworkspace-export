# Changelog
All notable changes to this project will be documented in this file.

## [Unreleased]

A summary of changes being worked.

### Added
- HTML files for messages in addition to current CSVs
- Relative, local links to files from the messages
- Human readable printing of links, @mentions, etc in messages (especially in the exported HTML)
- Standalone MacOS and Windows executables
- Make it easier to get your authentication token and pass it to the tool
- More interactive prompts for options

### Changed
- Change the message file names from organization from folder per year and file per month (`yyyy/messages {m}.csv`) to file per month with more conventional naming (`{yyyy.mm} messages.csv`) for message files. This will locate all messages a single directory per space since there won't be more than a couple years for most exports. This format will make the numbering more obviously a month as well. This will be a breaking change in a sense that newly exported spaces will have a different format, and resume will no longer work from those earlier exports.

## [0.1.0] - 2018-12-12
Initial version for changelog tracking - documenting current state

### Added
- Main python script. Support for use as a Python script assuming Python is already properly installed.
- Exports messages, files, and members
- Command line options for DMs, SPACEs, both or a particular space by ID
- Some metadata files, especially for files and the complete space
- Resumable. The tool will look at the messages file to see the last exported message and attempt to restart from that point.
