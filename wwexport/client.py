import requests
import json
import logging
import datetime
import time

graphql_url = "https://api.watsonwork.ibm.com/graphql"
logger = logging.getLogger("wwexport")
last_request = None
user_cache = {}

min_interval = datetime.timedelta(seconds=2)

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
    pass

def graphql_request(auth_token: str, request: str, params: str = None) -> requests.Response:
    global last_request
    now = datetime.datetime.now()
    if last_request:
        elapsed = now - last_request
        logger.debug("elapsed time since last request %s", elapsed)
        if elapsed < min_interval:
            wait = (min_interval-elapsed).total_seconds()
            logger.debug("waiting for %s seconds", wait)
            time.sleep(wait)

    last_request = now
    if params:
        logger.debug("POST %s\n%s\n%s", graphql_url, request, params)
    else:
        logger.debug("POST %s\n%s", graphql_url, request)
    response = requests.post(graphql_url, data=request, params=params, headers=get_headers(auth_token))
    if response.status_code == 401:
        raise UnauthorizedRequestError()
    elif response.status_code != 200:
        raise UnknownRequestError(response)
    return response

def get_headers(auth_token: str) -> dict:
    return {'jwt': auth_token, 'Content-Type': 'application/graphql', 'x-graphql-view': 'TYPED_ANNOTATIONS,EXPERIMENTAL,PUBLIC'}

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


def get_space_members (spaceId:str, after:str, auth_token:str) -> list:
    logger.info("Getting members for space %s starting after %s", spaceId, after)
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
        params = {'variables':'''{{"after": "{}","spaceId": "{}"}}'''.format(after, spaceId)}
    else:
        params = {'variables':'''{{"spaceId": "{0}"}}'''.format(spaceId)}
    response = graphql_request(request=request, params=params, auth_token=auth_token)
    space_members = handle_json_response(response, ("data","space","members"))
    return space_members



def get_space_messages (spaceId:str, oldest_timestamp:str, auth_token:str) -> list:
    logger.info("Getting messages for space %s starting at %s", spaceId, oldest_timestamp)

    request = """query getMessages($spaceId: ID!, $oldestTimestamp: Long) {
  space(id: $spaceId) {
    conversation {
      messages(last: 200, oldestTimestamp: $oldestTimestamp) {
        pageInfo {
          hasNextPage
          endCursor
        }
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
        params = {"variables":'''{{"oldestTimestamp": "{:d}","spaceId": "{}"}}'''.format(oldest_timestamp, spaceId)}
    else:
        params = {"variables":'''{{"spaceId": "{0}"}}'''.format(spaceId)}

    response = graphql_request(request=request, params=params, auth_token=auth_token)
    space_messages = handle_json_response(response, ("data","space","conversation","messages"))
    return space_messages
