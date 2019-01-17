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

from wwexport import constants

import json
import urllib
import sys
import argparse
import logging
import datetime
from abc import abstractmethod
from pathlib import Path

logger = logging.getLogger("wwexport")


class RequestError(Exception):
    """Base class for exceptions."""
    pass


class UnauthorizedRequestError(RequestError):
    """401 received when attempting to authenticate your app credentials."""
    pass


class AuthToken():

    @abstractmethod
    def jwt_token(self) -> str:
        return ''

    def __str__(self):
        return self.jwt_token()


class JWTAuthToken(AuthToken):

    def __init__(self, jwt_or_path: str):
        if jwt_or_path is None:
            raise ValueError("auth token is None")
        # strip quotes for windows, and strip whitespace for MacOS
        path = Path(jwt_or_path.strip().strip("\""))
        try:
            if path.exists() and path.is_file():
                logger.info("Obtaining JWT from file %s", path)
                with open(path, "r", encoding=constants.FILE_ENCODING) as file:
                    self.jwt = file.read()
            else:
                # it could be we have a path like "token (1).txt"
                # when dropped in MacOS, this becomes "token\ \(1\).txt"
                # so let's try again but remove slashes
                path = Path("".join(jwt_or_path.strip().split("\\")))
                if path.exists() and path.is_file():
                    logger.info("Obtaining JWT from file %s", path)
                    with open(path, "r", encoding=constants.FILE_ENCODING) as file:
                        self.jwt = file.read()
                else:
                    logger.info("Obtaining JWT as direct input")
                    self.jwt = jwt_or_path
        except OSError:
            logger.info("Obtaining JWT as direct input")
            self.jwt = jwt_or_path

    def jwt_token(self):
        return self.jwt


class AppAuthToken(AuthToken):

    def __init__(self, app_id: str, app_secret: str):
        if app_id is None:
            raise ValueError("app_id is None")
        if app_secret is None:
            raise ValueError("app_secret is None")
        self.app_id = app_id
        self.app_secret = app_secret
        self.jwt = None
        self.full_response = None
        self.expires_in_secs = None
        self.request_time = None
        self.expiry_time = None

    def auth_as_app(self) -> str:
        logger.info("Getting access token for app")
        self.request_time = datetime.datetime.now()
        data = {'grant_type': 'client_credentials'}

        pw_manager = urllib.HTTPPasswordMgrWithDefaultRealm()
        pw_manager.add_password(None, constants.OAUTH_URL, self.app_id, self.app_secret)
        urllib.install_opener(urllib.build_opener(urllib.HTTPBasicAuthHandler(pw_manager)))

        request = urllib.Request(constants.OAUTH_URL, data=data, headers=constants.OAUTH_REQUEST_HEADERS)

        try:
            with urllib.request.urlopen(request) as response:
                self.full_response = json.loads(response.read())
                self.jwt = self.full_response["access_token"]
                self.expires_in_secs = datetime.timedelta(seconds=self.full_response["expires_in"])
                self.expiry_time = self.request_time + self.expires_in_secs - constants.JWT_TOKEN_REFRESH_BUFFER
                logger.log(5, "refreshed auth token at %s - token will expire in %s, with a buffer next refresh will be at %s", self.request_time, self.expires_in_secs, self.expiry_time)
                return self.full_response
        except urllib.error.HTTPError as err:
            logger.critical("Tried to authenticate an app, got error code %s with reason %s", err.code, err.reason)
            raise UnauthorizedRequestError()

    def jwt_token(self):
        refresh_needed = self.request_time is None or self.expires_in_secs is None or datetime.datetime.now() > self.expiry_time
        if refresh_needed:
            self.auth_as_app()
        else:
            logger.log(5, "No refresh of jwt needed")
        return self.jwt


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Auth utility for Watson Workspace. Will print a client credential to the console. Redirect the output if you do not want it viewable in your console.",
        epilog="For use with app IDs and secrets obtained from https://developer.watsonwork.ibm.com/apps")
    parser.add_argument(
        "--appid", required=True)
    parser.add_argument(
        "--appsecret", required=True)

    args = parser.parse_args()

    apptoken = AppAuthToken(args.appid, args.appsecret)

    credential = apptoken.auth_as_app()
    print(credential)


if __name__ == "__main__":
    main(sys.argv)
