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
import yaml
import argparse
import getpass
import logging
import logging.handlers


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Export utility for Watson Workspace",
        epilog="Source at https://github.ibm.com/jbrunn/watsonworkspace_export")
    parser.add_argument(
        "--jwt", help="JWT token for accessing Watson Work. If ommitted, you may enter interactively, but interactive mode may not work in some terminals due to input length limits.")
    parser.add_argument(
        "--spaceid", help="An optional ID of a space to export. If omitted, all spaces will be exported.")

    file_group = parser.add_argument_group("Files")
    file_group.add_argument("--files", action="store_true", help="Export files. Unless --allfiles is also specified, the tool will only download files since latest downloaded message of the space. If no messages were previously downloaded for the space, the --files and --allfiles are equivalent.")
    file_group.add_argument("--allfiles", action="store_true", help="Restart file downloads from the beginning of time. If you previously ran the tool to download messages, but not files, then you may want to use this option. This option will still detect duplicate files within a space and delete them after they are downloaded.")

    logging_group = parser.add_argument_group("Logging")
    logging_group.add_argument(
        "--consolelevel", default="INFO", help="DEBUG, INFO, WARN, or ERROR")
    logging_group.add_argument(
        "--logfile", help="log messages of --filelevel to this file, defaults to DEBUG")
    logging_group.add_argument(
        "--filelevel", default="DEBUG", help="DEBUG, INFO, WARN, or ERROR")

    args = parser.parse_args()

    logger = logging.getLogger("wwexport")
    logging.addLevelName(5, "FINEST")

    default_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)-8s: %(message)s")

    error_log_handler = logging.handlers.RotatingFileHandler(
        "errors.log", maxBytes=1048576, backupCount=10)
    error_log_handler.setFormatter(default_formatter)
    error_log_handler.setLevel(logging.WARN)
    logger.addHandler(error_log_handler)

    if args.logfile:
        file_log_handler = logging.handlers.RotatingFileHandler(
            args.logfile, maxBytes=1048576, backupCount=10)
        file_log_handler.setFormatter(default_formatter)
        file_log_handler.setLevel(args.filelevel)
        logger.addHandler(file_log_handler)

    console_log_handler = logging.StreamHandler(stream=sys.stderr)
    console_log_handler.setLevel(args.consolelevel)
    logger.addHandler(console_log_handler)

    logger.setLevel(5)

    auth_token = args.jwt

    if not auth_token:
        auth_token = getpass.getpass("Watson Work Auth Token (JWT): ")

    logger.info("Starting export")

    try:
        if args.spaceid:
            space = client.get_space(args.spaceid, auth_token)
            core.export_space(space, auth_token, True, True,
                              args.files or args.allfiles, args.allfiles)
        else:
            spaces = core.get_all_spaces(auth_token)
            for space in spaces:
                core.export_space(space, auth_token, True, True,
                                  args.files or args.allfiles, args.allfiles)
    except client.UnauthorizedRequestError:
        logger.error("Export incomplete. Looks like your JWT might have timed out. Good thing this is resumable. Go get a new one and run this again. We'll pick up from where we left off (more or less).")
    except client.UnknownRequestError as err:
        logger.exception(
            "Export incomplete. Aborting with HTTP status code %s with response %s", err.status_code, err.text)
    except client.GraphQLError as err:
        logger.exception("Export incomplete. Terminating with GraphQLError. If problem persists, run with a log file enabled and check the prior request. You may also run the export space by space to avoid problematic content.")
    else:
        logger.info("Completed export")


if __name__ == "__main__":
    main(sys.argv)
