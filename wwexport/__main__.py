import core
import client
import sys
import yaml
import argparse
import getpass
import logging
import logging.handlers

def get_auth_token() -> str:
    return getpass.getpass("Watson Work Auth Token (JWT): ")

def get_refresh_token() -> str:
    return getpass.getpass("Watson Work Auth Refresh Token: ")

def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Export utility for Watson Workspace",
        epilog="Source at https://github.ibm.com/jbrunn/watsonworkspace_export")
    parser.add_argument("--jwt", help="JWT token for accessing Watson Work. If ommitted, you may enter interactively, but interactive mode may not work in some terminals due to input length limits.")
    parser.add_argument("--spaceid", help="An optional ID of a space to export. If omitted, all spaces will be exported.")
    parser.add_argument("-f", "--files", action="store_true", help="export files")

    logging_group = parser.add_argument_group("Logging")
    logging_group.add_argument("--consolelevel", default="INFO", help="DEBUG, INFO, WARN, or ERROR")
    logging_group.add_argument("--logfile", help="log all (DEBUG, INFO, WARN, ERROR) messages to this file")

    args = parser.parse_args()

    logger = logging.getLogger("wwexport")

    if args.logfile:
        file_log_handler = logging.handlers.RotatingFileHandler(args.logfile, maxBytes=1048576, backupCount=10)
        file_log_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)-8s: %(message)s")
        file_log_handler.setFormatter(debug_formatter)
        logger.addHandler(file_log_handler)

    console_log_handler = logging.StreamHandler(stream=sys.stderr)
    if args.consolelevel:
        console_log_handler.setLevel(args.consolelevel)
    else:
        console_log_handler.setLevel(logging.INFO)
    logger.addHandler(console_log_handler)
    logger.setLevel(logging.DEBUG)

    auth_token = args.jwt

    if not auth_token:
        auth_token = get_auth_token()

    logger.info("Starting export")

    try:
        if args.spaceid:
            space = client.get_space(args.spaceid, auth_token)
            core.export_space(space, auth_token, True, True, args.files)
        else:
            spaces = core.get_all_spaces(auth_token)
            for space in spaces:
                core.export_space(space, auth_token, True, True, args.files)
    except client.UnauthorizedRequestError:
        logger.error("Export incomplete. Looks like your JWT might have timed out. Good thing this is resumable. Go get a new one and run this again. We'll pick up from where we left off (more or less).")
    except client.UnknownRequestError as err:
        logger.error("Export incomplete. Aborting with HTTP status code %s with response %s", err.status_code, err.text)
    else:
        logger.info("Completed export")

if __name__ == "__main__":
    main(sys.argv)
