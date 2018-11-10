import datetime

MESSAGES_FILE_NAME_PATTERN = "messages {}.csv"
FILES_META_FOLDER = "_meta"
FILE_ENTRIES_FILE_NAME = "entries.json"
FILE_PATHS_FILE_NAME = "paths.json"

GRAPHQL_URL = "https://api.watsonwork.ibm.com/graphql"
GRAPHQL_VIEWS = "DIRECT_MESSAGING,RESOURCE,TYPED_ANNOTATIONS,EXPERIMENTAL,PUBLIC"

FILE_DOWNLOAD_URL_FORMAT = "https://api.watsonwork.ibm.com/files/api/v1/files/file/{}/content/noredirect"

MIN_GRAPHQL_INTERVAL = datetime.timedelta(seconds=2)
FILE_DOWNLOAD_WAIT = 2  # seconds
