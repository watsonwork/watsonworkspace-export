# Copyright 2018-2019 IBM
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

from wwexport import constants

import json
import urllib
import sys
import argparse
import logging
import datetime
from abc import abstractmethod

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

    def __init__(self, jwt: str):
        if jwt is None:
            raise ValueError("jwt is None")
        self.jwt = jwt

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
