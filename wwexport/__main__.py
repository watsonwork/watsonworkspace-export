# Copyright 2018 IBM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import core
import client
import sys
import argparse
import getpass
import logging
import logging.handlers
from enum import Enum
from pathlib import Path

export_root = Path.home() / "Watson Workspace Export"
debug_file_name = "debug.log"
error_file_name = "errors.log"


class SpaceType(Enum):
    spaces = "SPACE"
    dms = "DM"
    all = "ALL"

    def __str__(self):
        return self.value


class LogLevel(Enum):
    none = "NONE"
    finest = "FINEST"
    debug = "DEBUG"
    info = "INFO"
    warn = "WARN"
    error = "ERROR"

    def __str__(self):
        return self.value


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Export utility for Watson Workspace. This utility will create a directory at `{}` to export to.".format(export_root),
        epilog="For example, to export spaces without files, run `python wwexport`. To export spaces with files, run `python wwexport --files=ALL`. To export all spaces and DMs with all files, run `python wwexport --type=ALL --files=ALL`. Always check the {} file in your export directory. Source at https://github.ibm.com/jbrunn/watsonworkspace_export".format(error_file_name))
    parser.add_argument(
        "--jwt", help="JWT token for accessing Watson Work. If ommitted, you may enter interactively, but interactive mode may not work in some terminals due to input length limits.")

    space_args = parser.add_mutually_exclusive_group()
    space_args.add_argument(
        "--spaceid", help="An optional ID of a space or DM to export. If omitted, all spaces of the type specified will be exported.")
    space_args.add_argument("--type", type=SpaceType, choices=list(SpaceType), default=SpaceType.spaces, help="Export team spaces, DMs, or all. This parameter is ignored if a space ID is specified.")

    parser.add_argument("--files", type=core.FileOptions, choices=list(core.FileOptions), default=core.FileOptions.none, help="Specify how files will be exported, if at all. RESUME will only look at files since the most recently downloaded message. RESUME is useful if you have previously downloaded all files and just want to get any new content. ALL will page through metadata for all files to make sure older files are downloaded. Both options use a local metadata file to skip unnecessary downloads, and both options deduplicate among files in the space with the same name after downloading. You shouldn't have to worry about duplicate files, even if you use the ALL option multiple times. RESUME will be faster, but only use it if you are sure you have all files up to the latest local file already downloaded. If you are unsure, or this is the first time you are downloading files, ALL is suggested.")

    logging_group = parser.add_argument_group("logging")
    logging_group.add_argument(
        "--consolelevel", type=LogLevel, default=LogLevel.info, choices=list(LogLevel), help="Console log level")
    logging_group.add_argument(
        "--loglevel", type=LogLevel, default=LogLevel.none, choices=list(LogLevel), help="Messages of this type will be printed to a {} file in the export directory. Regardless, errors and warnings are ALWAYS printed to a separate {}.".format(debug_file_name, error_file_name))

    args = parser.parse_args()

    logger = logging.getLogger("wwexport")
    # set to the the finest level on the top level logger - the actual LogLevel
    # is controled by the handlers
    logging.addLevelName(5, "FINEST")
    logger.setLevel(5)
    default_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)-8s: %(message)s")

    # error log
    error_log_handler = logging.handlers.RotatingFileHandler(
        export_root / error_file_name, maxBytes=1048576, backupCount=10)
    error_log_handler.setFormatter(default_formatter)
    error_log_handler.setLevel(logging.WARN)
    logger.addHandler(error_log_handler)

    # optional debug log
    if args.loglevel and args.loglevel != LogLevel.none:
        file_log_handler = logging.handlers.RotatingFileHandler(
            export_root / debug_file_name, maxBytes=1048576, backupCount=10)
        file_log_handler.setFormatter(default_formatter)
        file_log_handler.setLevel(str(args.loglevel))
        logger.addHandler(file_log_handler)

    console_log_handler = logging.StreamHandler(stream=sys.stderr)
    console_log_handler.setLevel(str(args.consolelevel))
    logger.addHandler(console_log_handler)

    # auth
    auth_token = args.jwt
    if not auth_token:
        auth_token = getpass.getpass("Watson Work Auth Token (JWT): ")

    # let's do this!
    logger.info("Starting export")

    try:
        spaces_to_export = []
        if args.spaceid:
            spaces_to_export.append(client.get_space(args.spaceid, auth_token))
        else:
            if args.type == SpaceType.spaces or args.type == SpaceType.all:
                spaces_to_export.extend(core.get_all_team_spaces(auth_token))

            if args.type == SpaceType.dms or args.type == SpaceType.all:
                spaces_to_export.extend(core.get_all_dm_spaces(auth_token))

        for space in spaces_to_export:
            core.export_space(space, auth_token, export_root, args.files)

    except client.UnauthorizedRequestError:
        logger.error("Export incomplete. Looks like your JWT might have timed out or is invalid. Good thing this is resumable. Go get a new one and run this again. We'll pick up from where we left off (more or less).")
        sys.exit(1)
    except client.UnknownRequestError as err:
        logger.exception(
            "Export incomplete. Aborting with HTTP status code %s with response %s. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space.", err.status_code, err.text)
        sys.exit(1)
    except client.GraphQLError:
        logger.exception("Export incomplete. Terminating with GraphQLError. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space.")
        sys.exit(1)
    else:
        logger.info("Completed export")
        sys.exit(0)


if __name__ == "__main__":
    main(sys.argv)
