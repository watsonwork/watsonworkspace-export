import requests
import json
import logging
import datetime
import time
import filecmp
from pathlib import PurePath

graphql_url = "https://api.watsonwork.ibm.com/graphql"
file_url_format = "https://api.watsonwork.ibm.com/files/api/v1/files/file/{}/content/noredirect"
logger = logging.getLogger("wwexport")
last_graphql_request = None
user_cache = {}

min_graphql_interval = datetime.timedelta(seconds=2)
file_download_wait = 2 #seconds

class RequestError(Exception):
    """Base class for exceptions."""
    pass

class UnauthorizedRequestError(RequestError):
    """401 received from a service. JWT may have expired."""
    pass

class UnknownRequestError(RequestError):
    """Something else went wrong."""
    def __init__(self, response:requests.Response):
        self.status_code = response.status_code
        self.text = response.text

def download_file (file_id:str, file_title:str, folder:PurePath, auth_token:str) -> int:
    logger.info("Downloading file %s with title %s", file_id, file_title)
    file_url = file_url_format.format(file_id)

    logger.debug("waiting for %s seconds", file_download_wait)
    time.sleep(file_download_wait)

    response = requests.get(file_url, stream=True, headers=get_download_headers(auth_token))
    if response.status_code == 401:
        raise UnauthorizedRequestError()
    elif response.status_code != 200:
        raise UnknownRequestError(response)

    bytes_written = 0

    temp_file_path = folder / file_id

    try:
        # download to a temp file by using the id as the file name
        with open(temp_file_path, "wb") as local_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    local_file.write(chunk)
                    bytes_written += len(chunk)

        base_file_path = folder / file_title
        candidate_file_path = base_file_path

        # compare to files with the same title, if it's new, keep it with an
        # appropriate name
        found = False
        i = 1
        while candidate_file_path.exists() and not found:
            if filecmp.cmp(candidate_file_path, temp_file_path, shallow=False):
                logger.debug("file %s is the same as %s previously downloaded", temp_file_path, candidate_file_path)
                temp_file_path.unlink()
                found = True
            else:
                logger.debug("file %s is different %s", temp_file_path, candidate_file_path)
                candidate_file_path = folder / base_file_path.stem / i / base_file_path.suffixes
                i+=1
        if not found:
            temp_file_path.rename(candidate_file_path)
            logger.debug("file %s saved as %s", temp_file_path, candidate_file_path)
    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()

    logger.debug("wrote %s bytes", bytes_written)
    return bytes_written

def get_download_headers(auth_token: str) -> dict:
    return {'jwt': auth_token}

def graphql_request(auth_token: str, request: str, params: str = None) -> requests.Response:
    global last_graphql_request
    now = datetime.datetime.now()
    if last_graphql_request:
        elapsed = now - last_graphql_request
        logger.debug("elapsed time since last graphql request %s", elapsed)
        if elapsed < min_graphql_interval:
            wait = (min_graphql_interval-elapsed).total_seconds()
            logger.debug("waiting for %s seconds", wait)
            time.sleep(wait)

    last_graphql_request = now
    if params:
        logger.debug("POST %s\n%s\n%s", graphql_url, request, params)
    else:
        logger.debug("POST %s\n%s", graphql_url, request)
    response = requests.post(graphql_url, data=request, params=params, headers=get_graphql_headers(auth_token))
    if response.status_code == 401:
        raise UnauthorizedRequestError()
    elif response.status_code != 200:
        raise UnknownRequestError(response)
    return response

def get_graphql_headers(auth_token: str) -> dict:
    return {'jwt': auth_token, 'Content-Type': 'application/graphql', 'x-graphql-view': 'RESOURCE,TYPED_ANNOTATIONS,EXPERIMENTAL,PUBLIC'}

def handle_json_response(response:requests.Response, referenceToGet:list) -> dict:
    next_level = response.json()
    for next_label in referenceToGet:
        if (next_level[next_label]):
            next_level = next_level[next_label]
        else:
            return None
    return next_level

def get_user (user_id:str, auth_token:str) -> dict:
    logger.info("Getting user %s", user_id)
    if (user_id in user_cache):
        return user_cache[user_id]
    request = '''{{person(id:"{0}"){{email,displayName}}}}'''.format(user_id)

    response = graphql_request(request=request, auth_token=auth_token)
    user = handle_json_response(response, ("data", "person"))
    user_cache[user_id] = user
    return user

def get_space (space_id:str, auth_token:str) -> dict:
    logger.info("Getting space %s", space_id)
    request = """query getSpace($spaceId: ID!) {
  space(id: $spaceId) {
    title
    id
  }
}"""
    params = {'variables':'''{{"spaceId": "{0}"}}'''.format(space_id)}
    response = graphql_request(request=request, params=params, auth_token=auth_token)
    return handle_json_response(response, ("data","space"))

def get_spaces (after:str, auth_token:str) -> list:
    logger.info("Getting spaces starting after %s", after)
    request = """query getSpaces($after: String) {
  spaces(first: 200, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    items {
      title
      id
    }
  }
}"""
    params = {}
    if (after):
        params = {'variables':'''{{"after": "{0}"}}'''.format(after)}
    response = graphql_request(request=request, params=params, auth_token=auth_token)
    return handle_json_response(response, ("data","spaces"))


def get_space_members (space_id:str, after:str, auth_token:str) -> list:
    logger.info("Getting members for space %s starting after %s", space_id, after)
    request = """query getMembers($spaceId: ID!, $after: String) {
  space(id: $spaceId) {
     members(first: 200, after: $after) {
      pageInfo {
        hasNextPage
        endCursor
      }
      items {
        id
        displayName
        email
      }
    }
  }
}"""
    if (after):
        params = {'variables':'''{{"after": "{}","spaceId": "{}"}}'''.format(after, space_id)}
    else:
        params = {'variables':'''{{"spaceId": "{0}"}}'''.format(space_id)}
    response = graphql_request(request=request, params=params, auth_token=auth_token)
    space_members = handle_json_response(response, ("data","space","members"))
    return space_members

def get_space_files (space_id:str, oldest_timestamp:str, auth_token:str) -> list:
    logger.info("Getting files for space %s starting at %s", space_id, oldest_timestamp)

    request = """query getFiles($spaceId: ID!, $oldestTimestamp: Long) {
  space(id: $spaceId) {
    resources(last: 200, oldestTimestamp: $oldestTimestamp) {
      items {
        id
        title
        created
      }
    }
  }
}
"""
    if (oldest_timestamp):
        params = {"variables":'''{{"oldestTimestamp": "{:d}","spaceId": "{}"}}'''.format(oldest_timestamp, space_id)}
    else:
        params = {"variables":'''{{"spaceId": "{0}"}}'''.format(space_id)}

    response = graphql_request(request=request, params=params, auth_token=auth_token)
    space_files = handle_json_response(response, ("data","space","resources","items"))
    return space_files

def get_space_messages (space_id:str, oldest_timestamp:str, auth_token:str) -> list:
    logger.info("Getting messages for space %s starting at %s", space_id, oldest_timestamp)

    request = """query getMessages($spaceId: ID!, $oldestTimestamp: Long) {
  space(id: $spaceId) {
    conversation {
      messages(last: 200, oldestTimestamp: $oldestTimestamp) {
        items {
          id
          content
          createdBy {
            id
            displayName
          }
          created
          typedAnnotations(include: GENERIC) {
            ... on GenericAnnotation {
              text
              title
            }
          }
        }
      }
    }
  }
}"""
    if (oldest_timestamp):
        params = {"variables":'''{{"oldestTimestamp": "{:d}","spaceId": "{}"}}'''.format(oldest_timestamp, space_id)}
    else:
        params = {"variables":'''{{"spaceId": "{0}"}}'''.format(space_id)}

    response = graphql_request(request=request, params=params, auth_token=auth_token)
    space_messages = handle_json_response(response, ("data","space","conversation","messages","items"))
    return space_messages
