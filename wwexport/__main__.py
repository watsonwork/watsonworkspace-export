# MIT License
#
# Copyright 2018-2019 IBM
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

from wwexport import core
from wwexport import queries
from wwexport import auth
from wwexport import constants
from wwexport import ww_html
from wwexport import env
from wwexport import messages

import urllib
import sys
import argparse
import json
import logging
from enum import Enum

debug_file_name = "debug.log"
error_file_name = "errors.log"


class SpaceType(Enum):
    spaces = "SPACE"
    dms = "DM"
    all = "ALL"

    def __str__(self):
        return self.value


def main(argv):
    error = False
    html_gen_errors = []

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Export utility for Watson Workspace, build {}".format(env.build_info),
        epilog="For example, to export all Spaces and DM with files, run `python -m wwexport`. Always check the {} file in your export directory. Source at https://github.com/watsonwork/watsonworkspace-export".format(error_file_name))

    env.add_export_root_args(parser)

    auth_group = parser.add_mutually_exclusive_group()

    auth_group.add_argument(
        "--appcred", help="App credentials specified as appId:appSecret, obtained for an app from https://developer.watsonwork.ibm.com/apps. If both AppCred and JWT are specified, JWT is ignored. If AppCred is used, spaces to which the app has been directly added will be available for export.")
    auth_group.add_argument(
        "--jwt", help="JWT token for accessing Watson Work, or a path to a file containing the JWT as plaintext. If both JWT and AppCred are omitted, you may supply a JWT or path to JWT interactively. The JWT may be obtained from https://workspace.ibm.com/exporttoken.")

    space_args = parser.add_mutually_exclusive_group()
    space_args.add_argument(
        "--spaceid", help="An optional ID of a space or DM to export. If omitted, all spaces of the type specified will be exported.")
    space_args.add_argument("--type", type=SpaceType, choices=list(SpaceType), default=SpaceType.all, help="Export team spaces, DMs, or all. This parameter is ignored if a space ID is specified.")

    parser.add_argument("--files", type=core.FileOptions, choices=list(core.FileOptions), default=core.FileOptions.all, help="Specify how files will be exported, if at all. RESUME will only look at files since the most recently downloaded message. RESUME is useful if you have previously downloaded all files and just want to get any new content. ALL will page through metadata for all files to make sure older files are downloaded. Both options use a local metadata file to skip unnecessary downloads, and both options deduplicate among files in the space with the same name after downloading. You shouldn't have to worry about duplicate files, even if you use the ALL option multiple times. RESUME will be faster, but only use it if you are sure you have all files up to the latest local file already downloaded. If you are unsure, or this is the first time you are downloading files, ALL is suggested.")

    parser.add_argument("--annotations", action="store_true", help="Write all annotations in the message files. Even without this option, the content of a generic annotation will be exported if there is no other message content.")

    parser.add_argument("--graphqlerror", type=env.OnError, choices=list(env.OnError), default=env.OnError.exit, help="Determines how certain GraphQL errors are handled. Use with caution as this can cause some errors to be written to the log, but otherwise ignored. Recommended to use this only in conjunction with the spaceid parameter to limit the use to problematic content. This does not affect certain HTML generation and even permission denied errors embedded in GraphQL which will always continue, regardless of this setting. This setting only affects unexpected errors inside GraphQL responses, allowing the program to continue even when the server returns some errors on particular content.")

    env.add_logger_args(parser)

    args = parser.parse_args()

    env.config_export_root(args)
    env.config_logger(args)
    logger = logging.getLogger("wwexport")

    # error handling
    if args.graphqlerror:
        env.on_graphql_error = args.graphqlerror

    logger.info("wwexport - running build %s", env.build_info)

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
        print(messages.WELCOME.format(env.export_root))
        auth_token = auth.JWTAuthToken(input(messages.AUTH_PROMPT))

    # let's do this!

    logger.info("Starting export")
    print("""
Exporting to {}""".format(env.export_root))

    try:
        spaces_to_export = []
        if args.spaceid:
            spaces_to_export.append(queries.space.execute(auth_token, spaceid=args.spaceid))
        else:
            if args.type == SpaceType.spaces or args.type == SpaceType.all:
                spaces = queries.team_spaces.all_pages(auth_token)
                with open(env.export_root / "spaces.json", "w+", encoding=constants.FILE_ENCODING) as f:
                    json.dump(spaces, f)
                spaces_to_export.extend(spaces)

            if args.type == SpaceType.dms or args.type == SpaceType.all:
                dm_spaces = queries.dm_spaces.all_pages(auth_token)
                with open(env.export_root / "dms.json", "w+", encoding=constants.FILE_ENCODING) as f:
                    json.dump(dm_spaces, f)
                spaces_to_export.extend(dm_spaces)

        space_progress = env.progress_bar(spaces_to_export,
                                          desc="Export Spaces",
                                          position=0,
                                          unit="space",
                                          )
        for space in space_progress:
            # core export (CSV and files)
            space_root, space_display_name = core.export_space(space,
                                                               auth_token,
                                                               env.export_root,
                                                               args.files,
                                                               export_annotations=args.annotations,
                                                               space_progress=space_progress)

            html_gen_errors.extend(ww_html.space_to_htmls(space_root, space_display_name))

    except queries.UnauthorizedRequestError:
        msg = "\nExport incomplete. Looks like your authorization token might have timed out or is invalid. Good thing this is resumable. Get a new token from https://workspace.ibm.com/exporttoken and run this again. We'll pick up from where we left off (more or less)."
        print(msg)
        logger.error(msg)
    except queries.UnknownRequestError as err:
        logger.exception(
            "Export incomplete. Aborting with HTTP status code %s and reason %s. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space.", err.status_code, err.reason)
        error = True
    except queries.GraphQLError:
        logger.exception("Export incomplete. Terminating with GraphQLError. If problem persists, run with a debug enabled and check the prior request. You may also run the export space by space. Consider using the --graphqlerror CONTINUE option if this persists and you are unable to export content.")
        error = True
    except urllib.error.URLError:
        logger.exception("Export incomplete. Problem with the HTTP Connection. Restart the export and it will resume where you left off (for the most part).")
        error = True
    except auth.UnauthorizedRequestError:
        logger.exception("Export incomplete. Unable to authenticate or reauthenticate.")
        error = True
    except Exception:
        logger.exception("Export incomplete. Unknown error.")
        error = True
    else:
        msg = "\nCompleted export\n"
        logger.info(msg)
        print(msg)
        sys.exit(0)

    if len(html_gen_errors) > 0:
        msg = "\nThe following CSV message files could not be converted to HTML. Data has only been saved to CSV for these files. Rerunning the export may NOT attempt to regenerate these files - it is not expected that a retry will not help with these files. Check the {} and {} files in your export directory for more information.\n{}".format(debug_file_name, error_file_name, "\n".join([str(p) for p in html_gen_errors]))
        logger.error(msg)
        print(msg)

    if error:
        msg = "\nAn error interrupted the export from completing. You may first want to retry the export and see if this error presists. Some errors, such as internet connection issues, will interrupt the export, but running again can continue where you left off. If this message persists, check the {} and {} files in your export directory for more information.".format(debug_file_name, error_file_name)
        logger.critical(msg)
        print(msg)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)
