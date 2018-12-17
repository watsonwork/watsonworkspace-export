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

from wwexport import core
from wwexport import queries
from wwexport import auth
from wwexport import constants

import requests
import sys
import argparse
import getpass
import json
import logging
import logging.handlers
from enum import Enum
from pathlib import Path

from tqdm import tqdm

default_export_root = Path.home() / "Watson Workspace Export"
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
        description="Export utility for Watson Workspace.",
        epilog="For example, to export spaces without files, run `python wwexport`. To export spaces with files, run `python wwexport --files=ALL`. To export all spaces and DMs with all files, run `python wwexport --type=ALL --files=ALL`. Always check the {} file in your export directory. Source at https://github.com/watsonwork/watsonworkspace-export".format(error_file_name))

    parser.add_argument("--dir", default=default_export_root, help="Directory to export to. This directory will be created if it doesn't exist.")

    auth_group = parser.add_mutually_exclusive_group()

    auth_group.add_argument(
        "--appcred", help="App credentials specified as appId:appSecret, obtained for an app from https://developer.watsonwork.ibm.com/apps. If both AppCred and JWT are specified, JWT is ignored. If AppCred is used, spaces to which the app has been directly added will be available for export.")
    auth_group.add_argument(
        "--jwt", help="JWT token for accessing Watson Work. If both JWT and AppCred are omitted, you may enter a JWT interactively, but interactive mode may not work in some terminals due to input length limits.")

    space_args = parser.add_mutually_exclusive_group()
    space_args.add_argument(
        "--spaceid", help="An optional ID of a space or DM to export. If omitted, all spaces of the type specified will be exported.")
    space_args.add_argument("--type", type=SpaceType, choices=list(SpaceType), default=SpaceType.spaces, help="Export team spaces, DMs, or all. This parameter is ignored if a space ID is specified.")

    parser.add_argument("--files", type=core.FileOptions, choices=list(core.FileOptions), default=core.FileOptions.none, help="Specify how files will be exported, if at all. RESUME will only look at files since the most recently downloaded message. RESUME is useful if you have previously downloaded all files and just want to get any new content. ALL will page through metadata for all files to make sure older files are downloaded. Both options use a local metadata file to skip unnecessary downloads, and both options deduplicate among files in the space with the same name after downloading. You shouldn't have to worry about duplicate files, even if you use the ALL option multiple times. RESUME will be faster, but only use it if you are sure you have all files up to the latest local file already downloaded. If you are unsure, or this is the first time you are downloading files, ALL is suggested.")

    parser.add_argument("--annotations", action="store_true", help="Incude this option to write all annotations in the message files. Even without this option, the content of a generic annotation will be exported if there is no other message content.")

    logging_group = parser.add_argument_group("logging")
    logging_group.add_argument(
        "--loglevel", type=LogLevel, default=LogLevel.info, choices=list(LogLevel), help="Messages of this type will be printed to a {} file in the export directory. Regardless, errors and warnings are ALWAYS printed to a separate {}.".format(debug_file_name, error_file_name))

    args = parser.parse_args()

    export_root = Path(args.dir)
    export_root.mkdir(exist_ok=True, parents=True)

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

    # auth
    auth_token = None
    appcred = args.appcred
    if appcred:
        appcred_list = appcred.split(":")
        if len(appcred_list) != 2:
            logger.critical("Invalid AppCred format. The AppCred should have your appID and appSecret separated by a single colon (:). It appears there are %s colons in your appcred.", len(appcred_list) - 1)
            sys.exit(1)
        else:
            auth_token = auth.AppAuthToken(appcred_list[0], appcred_list[1])
    elif args.jwt:
        auth_token = auth.JWTAuthToken(args.jwt)
    else:
        auth_token = auth.JWTAuthToken(getpass.getpass("Watson Work Auth Token (JWT): "))

    # let's do this!

    logger.info("Starting export")

    try:
        spaces_to_export = []
        if args.spaceid:
            spaces_to_export.append(queries.space.execute(auth_token, spaceid=args.spaceid))
        else:
            if args.type == SpaceType.spaces or args.type == SpaceType.all:
                spaces = queries.team_spaces.all_pages(auth_token)
                with open(export_root / "spaces.json", "w+", encoding=constants.FILE_ENCODING) as f:
                    json.dump(spaces, f)
                spaces_to_export.extend(spaces)

            if args.type == SpaceType.dms or args.type == SpaceType.all:
                dm_spaces = queries.dm_spaces.all_pages(auth_token)
                with open(export_root / "dms.json", "w+", encoding=constants.FILE_ENCODING) as f:
                    json.dump(dm_spaces, f)
                spaces_to_export.extend(dm_spaces)

        for space in tqdm(spaces_to_export, desc="Export Spaces", position=0, unit="space", dynamic_ncols=True):
            core.export_space(space, auth_token, export_root, args.files, export_annotations=args.annotations)

    except queries.UnauthorizedRequestError:
        logger.error("Export incomplete. Looks like your JWT might have timed out or is invalid. Good thing this is resumable. Go get a new one and run this again. We'll pick up from where we left off (more or less).")
        sys.exit(1)
    except queries.UnknownRequestError as err:
        logger.exception(
            "Export incomplete. Aborting with HTTP status code %s with response %s. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space.", err.status_code, err.text)
        sys.exit(1)
    except queries.GraphQLError:
        logger.exception("Export incomplete. Terminating with GraphQLError. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space.")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        logger.exception("Export incomplete. Connection was interrupted. Restart the export and it will resume where you left off (for the most part)")
        sys.exit(1)
    except auth.UnauthorizedRequestError:
        logger.exception("Export incomplete. Unable to authenticate or reauthenticate.")
        sys.exit(1)
    except Exception:
        logger.exception("Export incomplete. Unknown error.")
        sys.exit(1)
    else:
        logger.info("Completed export")
        sys.exit(0)


if __name__ == "__main__":
    main(sys.argv)
