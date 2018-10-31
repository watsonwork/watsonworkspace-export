import requests
import json

graphql_url = "https://api.watsonwork.ibm.com/graphql"

def get_headers(auth_token):
    return {'jwt': auth_token, 'Content-Type': 'application/graphql', 'x-graphql-view': 'TYPED_ANNOTATIONS,EXPERIMENTAL,PUBLIC'}

def handle_json_response(response, referenceToGet):
    if (response.status_code == 401):
        print ("Oops!! Check your JWT token and rerun this.")
    elif (response.status_code != 200):
        print ("Uh oh! Something went wrong!")
        print (response.json())
    else:
        next_level = response.json()
        for next_label in referenceToGet:
            if (next_level[next_label]):
                next_level = next_level[next_label]
            else:
                return None
        return next_level

users = {}
def get_user (user_id, auth_token):
    if (user_id in users):
        return users[user_id]
    request = '''{{person(id:"{0}"){{email,displayName}}}}'''.format(user_id)
    response = requests.post(graphql_url, data=request, headers=get_headers(auth_token))
    user = handle_json_response(response, ("data", "person"))
    users[user_id] = user
    return user

def get_spaces (after, auth_token):
    request = """
query getSpaces($after: String) {
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
}
"""
    params = {}
    if (after):
        params = {'variables':'''{{"after": "{0}"}}'''.format(after)}
    response = requests.post(graphql_url, data=request, params=params, headers=get_headers(auth_token))
    return handle_json_response(response, ("data","spaces"))


def get_space_members (spaceId, after, auth_token):
    request = """
query getMembers($spaceId: ID!, $after: String) {
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
}
"""
    if (after):
        params = {'variables':'''{{"after": "{}","spaceId": "{}"}}'''.format(after, spaceId)}
    else:
        params = {'variables':'''{{"spaceId": "{0}"}}'''.format(spaceId)}
    response = requests.post(graphql_url, data=request, params=params, headers=get_headers(auth_token))
    space_members = handle_json_response(response, ("data","space","members"))
    return space_members



def get_space_messages (spaceId, oldest_timestamp, auth_token):
    request = """
query getMessages($spaceId: ID!, $oldestTimestamp: Long) {
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
}

"""
    if (oldest_timestamp):
        params = {"variables":'''{{"oldestTimestamp": "{:d}","spaceId": "{}"}}'''.format(oldest_timestamp, spaceId)}
    else:
        params = {"variables":'''{{"spaceId": "{0}"}}'''.format(spaceId)}
    response = requests.post(graphql_url, data=request, params=params, headers=get_headers(auth_token))
    space_messages = handle_json_response(response, ("data","space","conversation","messages"))
    #print(response.json())
    return space_messages
