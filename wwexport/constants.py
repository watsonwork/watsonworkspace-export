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

import datetime

MESSAGES_FILE_NAME_PATTERN = "messages {}.csv"
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
