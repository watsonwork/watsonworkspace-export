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

import constants
import auth

import datetime
import requests
import logging
import json
import time
import filecmp
import os
from pathlib import PurePath

logger = logging.getLogger("wwexport")


class RequestError(Exception):
    """Base class for exceptions."""
    pass


class UnauthorizedRequestError(RequestError):
    """401 received from a service. JWT may have expired."""
    pass


class UnknownRequestError(RequestError):
    """Something else went wrong."""

    def __init__(self, response: requests.Response):
        self.status_code = response.status_code
        self.text = response.text


class GraphQLError(RequestError):
    """An error was detected inside the GraphQL response"""

    def __init__(self, errors: list):
        self.errors = errors


class Query:

    __last_graphql_request_time = None

    def __init__(self, name: str, query_string: str, key_reference: list = [], api_url: str = constants.GRAPHQL_URL, graphql_views: str = constants.GRAPHQL_VIEWS):
        self.name = name
        self.query_string = query_string
        self.key_reference = key_reference
        self.api_url = api_url
        self.graphql_views = graphql_views

    def __graphql_headers(self, auth_token: auth.AuthToken) -> dict:
        return {'jwt': auth_token.jwt_token(), 'Content-Type': 'application/graphql', 'x-graphql-view': self.graphql_views}

    @staticmethod
    def __handle_json_response(response: requests.Response, reference_to_get: list):
        next_level = response.json()
        logger.log(5, "response JSON\n%s", next_level)

        if "errors" in next_level:
            # we will continue on 403 errors embedded in the graphql response,
            # and just log them, but we'll stop on all other GraphQL errors.
            error_codes = set([error["message"].strip()
                               for error in next_level["errors"]])
            if "403" in error_codes:
                error_codes.remove("403")
            if len(error_codes) > 0:
                raise GraphQLError(next_level["errors"])
            else:
                logger.error(
                    "encountered permission denied (403) while fetching data %s", next_level)

        for next_label in reference_to_get:
            if (next_level[next_label]):
                next_level = next_level[next_label]
            else:
                return None
        return next_level

    def __graphql_request(self, auth_token: auth.AuthToken, request: str, params: str = None) -> requests.Response:
        now = datetime.datetime.now()
        if type(self).__last_graphql_request_time:
            elapsed = now - type(self).__last_graphql_request_time
            logger.debug("elapsed time since last graphql request %s", elapsed)
            if elapsed < constants.MIN_GRAPHQL_INTERVAL:
                wait = (constants.MIN_GRAPHQL_INTERVAL - elapsed).total_seconds()
                logger.log(5, "waiting for %s seconds", wait)
                time.sleep(wait)

        type(self).__last_graphql_request_time = now
        if params:
            logger.debug("POST %s\n%s\n%s", constants.GRAPHQL_URL, request, params)
        else:
            logger.debug("POST %s\n%s", constants.GRAPHQL_URL, request)
        response = requests.post(constants.GRAPHQL_URL, data=request, params=params,
                                 headers=self.__graphql_headers(auth_token))
        if response.status_code == 401:
            raise UnauthorizedRequestError()
        elif response.status_code != 200:
            raise UnknownRequestError(response)

        return response

    def execute(self, auth_token: auth.AuthToken, **kwargs: dict):
        params = {'variables': json.dumps(kwargs)} if kwargs is not None else {}
        logger.info("Executing query %s with params %s", self.name, params)
        response = self.__graphql_request(
            request=self.query_string, params=params, auth_token=auth_token)
        return self.__handle_json_response(response, self.key_reference)

    def all_pages(self, auth_token: auth.AuthToken, **kwargs: dict):
        """Iterately calls execute with the provided query, using standard
        pagination conventions, and using kwargs as variables in the query"""
        after = None
        all = []
        while True:
            if after:
                kwargs["after"] = after
            next_page = self.execute(auth_token, **kwargs)
            all.extend(next_page["items"])
            if (next_page["pageInfo"]["hasNextPage"]):
                after = next_page["pageInfo"]["endCursor"]
            else:
                break
        return all


def __download_headers(auth_token: auth.AuthToken) -> dict:
    return {'jwt': auth_token.jwt_token()}


def download(file_id: str, file_title: str, folder: str, auth_token: str):
    logger.info("Downloading file %s with title %s", file_id, file_title)
    download_url = constants.FILE_DOWNLOAD_URL_FORMAT.format(file_id)
    logger.debug("file url %s", download_url)

    logger.log(5, "waiting for %s seconds", constants.FILE_DOWNLOAD_WAIT)
    time.sleep(constants.FILE_DOWNLOAD_WAIT)

    response = requests.get(download_url, stream=True,
                            headers=__download_headers(auth_token))
    if response.status_code == 401:
        raise UnauthorizedRequestError()
    elif response.status_code == 204:
        content_location = response.headers["x-content-location"]
        response = requests.get(content_location, stream=True)
    elif response.status_code != 200:
        raise UnknownRequestError(response)

    bytes_written = 0
    new_file = False

    temp_file_path = os.path.normpath(os.path.join(folder, file_id))

    try:
        # download to a temp file by using the id as the file name
        with open(temp_file_path, "wb") as local_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    local_file.write(chunk)
                    bytes_written += len(chunk)
        logger.debug("wrote %s bytes", bytes_written)

        base_file_path = os.path.normpath(os.path.join(folder, file_title))
        candidate_file_path = base_file_path

        # compare to files with the same title, if it's new, keep it with an
        # appropriate name
        found = False
        i = 1
        while os.path.exists(candidate_file_path) and not found:
            if filecmp.cmp(candidate_file_path, temp_file_path, shallow=False):
                logger.debug("file %s is the same as %s previously downloaded",
                             temp_file_path, candidate_file_path)
                #temp_file_path.unlink()
                os.remove(temp_file_path)
                found = True
            else:
                logger.debug("file %s is different from %s",
                             temp_file_path, candidate_file_path)
                #candidate_file_path = folder / \
                #    "{} {}{}".format(base_file_path.stem, i,
                #                     ''.join(base_file_path.suffixes))
                base_file_path_pair = os.path.splitext(base_file_path)
                candidate_file_path = os.path.normpath(os.path.join(folder, "{} {}{}".format(base_file_path_pair[0], i,''.join(base_file_path_pair[1]))))
                i += 1
        if not found:
            new_file = True
            #temp_file_path.rename(candidate_file_path)
            os.rename(temp_file_path, candidate_file_path)
            logger.debug("file %s with id %s saved as %s",
                         file_title, file_id, candidate_file_path)
    finally:
        if os.path.exists(temp_file_path):
            #temp_file_path.unlink()
            os.remove(temp_file_path)

    return candidate_file_path, new_file


dm_spaces = Query("DM Spaces", """query getDMSpaces($after: String) {
  directMessagingSpaces(first: 200, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    items {
      id
      type
      members(first: 2) {
        items {
          id
          displayName
          email
        }
      }
    }
  }
}""", ["data", "directMessagingSpaces"])

team_spaces = Query("Team Spaces", """query getSpaces($after: String) {
  spaces(first: 200, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    items {
      title
      id
      type
    }
  }
}""", ["data", "spaces"])

space = Query("Space by ID", """query getSpace($spaceid: ID!) {
  space(id: $spaceid) {
    title
    id
    type
    members(first: 2) {
      items {
        id
        displayName
        email
      }
    }
  }
}""", ["data", "space"])

space_members = Query("Space Members", """query getMembers($spaceid: ID!, $after: String) {
  space(id: $spaceid) {
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
}""", ["data", "space", "members"])

space_files = Query("Space Files", """query getFiles($spaceid: ID!, $timestamp: Long) {
  space(id: $spaceid) {
    resources(first: 200, mostRecentTimestamp: $timestamp) {
      pageInfo {
        hasNextPage
        endCursor
      }
      items {
        id
        title
        created
        createdBy {
          id
          displayName
          email
        }
        contentType
        message {
          id
        }
      }
    }
  }
}""", ["data", "space", "resources", "items"])

space_messages = Query("Space Messages", """query getMessages($spaceid: ID!, $oldest: Long) {
  space(id: $spaceid) {
    conversation {
      messages(last: 200, oldestTimestamp: $oldest) {
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
}""", ["data", "space", "conversation", "messages", "items"])

space_messages_with_annotations = Query("Space Messages with Annotations", """query getMessages($spaceid: ID!, $oldest: Long) {
  space(id: $spaceid) {
    conversation {
      messages(last: 200, oldestTimestamp: $oldest) {
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
          annotations
        }
      }
    }
  }
}""", ["data", "space", "conversation", "messages", "items"])


current_user = Query("Current User",
                     "query getMe{me{id,displayName,email}}",
                     ["data", "me"])
