# MIT License
#
# Copyright 2019 IBM
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from wwexport import constants

import logging
import logging.handlers
import pkgutil
from enum import Enum
from tqdm import tqdm
from pathlib import Path


class LogLevel(Enum):
    none = "NONE"
    finest = "FINEST"
    debug = "DEBUG"
    info = "INFO"
    warn = "WARN"
    error = "ERROR"

    def __str__(self):
        return self.value


class OnError(Enum):
    exit = "EXIT"
    cont = "CONTINUE"

    def __str__(self):
        return self.value


export_root = Path.home() / "Watson Workspace Export"
on_graphql_error = OnError.exit

__build_info = "LOCAL SCRIPT"


try:
    buildtxt_binary = pkgutil.get_data("wwexport", "build.txt")
except FileNotFoundError:
    pass
else:
    build_info = buildtxt_binary.decode(constants.FILE_ENCODING, "ignore")


def progress_bar(iterable=None, desc=None, position=None, unit="", initial=0):
    return tqdm(iterable, desc=desc, position=position, unit=unit, initial=initial, leave=False if position > 0 else True, ncols=75)


def add_export_root_args(parser):
    parser.add_argument("--dir", default=export_root, help="Directory to export to. This directory will be created if it doesn't exist.")


def add_logger_args(parser):
    logging_group = parser.add_argument_group("logging")
    logging_group.add_argument(
        "--loglevel", type=LogLevel, default=LogLevel.info, choices=list(LogLevel), help="Messages of this type will be printed to a {} file in the export directory. Regardless, errors and warnings are ALWAYS printed to a separate {}.".format(constants.DEBUG_FILE_NAME, constants.ERROR_FILE_NAME))


def config_export_root(args):
    global export_root
    export_root = Path(args.dir)
    export_root.mkdir(exist_ok=True, parents=True)


def config_logger(args, logger_name="wwexport"):
    logger = logging.getLogger(logger_name)
    # set to the the finest level on the top level logger - the actual LogLevel
    # is controled by the handlers
    logging.addLevelName(5, "FINEST")
    logger.setLevel(5)
    default_formatter = logging.Formatter(
        "%(asctime)s %(name)s %(levelname)-8s: %(message)s")

    # error log
    error_log_handler = logging.handlers.RotatingFileHandler(
        export_root / constants.ERROR_FILE_NAME,
        maxBytes=1048576,
        backupCount=10,
        encoding=constants.FILE_ENCODING)
    error_log_handler.setFormatter(default_formatter)
    error_log_handler.setLevel(logging.WARN)
    logger.addHandler(error_log_handler)

    # optional debug log
    if args.loglevel and args.loglevel != LogLevel.none:
        file_log_handler = logging.handlers.RotatingFileHandler(
            export_root / constants.DEBUG_FILE_NAME,
            maxBytes=1048576,
            backupCount=10,
            encoding=constants.FILE_ENCODING)
        file_log_handler.setFormatter(default_formatter)
        file_log_handler.setLevel(str(args.loglevel))
        logger.addHandler(file_log_handler)


def get_messages_path(space_export_root: str, year: int, month: int) -> str:
    return space_export_root / constants.MESSAGES_FILE_NAME_PATTERN.format(year=year, month=month)
