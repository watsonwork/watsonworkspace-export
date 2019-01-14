# MIT License
#
# Copyright 2018 IBM
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

import datetime

REQUEST_ENCODING = "UTF-8"
FILE_ENCODING = "UTF-8"

MESSAGES_FILE_NAME_PATTERN = "{year}.{month} messages.csv"
FILES_META_FOLDER = "_meta"
FILE_ENTRIES_FILE_NAME = "entries.json"
FILE_PATHS_FILE_NAME = "paths.json"

OAUTH_URL = "https://api.watsonwork.ibm.com/oauth/token"
OAUTH_REQUEST_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
JWT_TOKEN_REFRESH_BUFFER = datetime.timedelta(seconds=60)

GRAPHQL_URL = "https://api.watsonwork.ibm.com/graphql"
GRAPHQL_VIEWS = "DIRECT_MESSAGING,RESOURCE,TYPED_ANNOTATIONS,EXPERIMENTAL,PUBLIC"

FILE_DOWNLOAD_URL_FORMAT = "https://api.watsonwork.ibm.com/files/api/v1/files/file/{}/content/noredirect"

MIN_GRAPHQL_INTERVAL = datetime.timedelta(seconds=2)
FILE_DOWNLOAD_WAIT = 2  # seconds

FILE_NAME_TRANSLATION_TABLE = str.maketrans("/\\<>|", "-----", ":\"?*")
