from . import requests

import os
import csv
import datetime
#import getpass
from pathlib import Path
from dateutil.parser import parse
from collections import namedtuple

messages_file_format = "messages {}.csv"

def get_auth_token():
    return input("Watson Work JWT: ")
    #return getpass.getpass("Watson Work JWT: ")

def get_all_spaces(auth_token):
    after = None
    all_spaces = []
    while True:
        spaces_page = requests.get_spaces(after, auth_token)
        all_spaces.extend(spaces_page["items"])

        if (spaces_page["pageInfo"]["hasNextPage"]):
            after = spaces_page["pageInfo"]["endCursor"]
        else:
            break
    return all_spaces

def export_space_members(space_id, filename, auth_token):
    with open(filename,"w+") as space_members_file:
        space_members_writer = csv.writer(space_members_file)
        space_members = []
        after = None
        while True:
            space_members_page = requests.get_space_members(space_id, after, auth_token)
            for member in space_members_page["items"]:
                space_members_writer.writerow([member["displayName"],member["email"],member["id"]])

            space_members.extend(space_members_page["items"])

            if (space_members_page["pageInfo"]["hasNextPage"]):
                after = space_members_page["pageInfo"]["endCursor"]
            else:
                break
    return space_members

def write_message(message, writer):
    # if there isn't content, pull it from the annotation if there is one
    if message["content"] is None:
        if message["typedAnnotations"] is not None:
            if len(message["typedAnnotations"]) >0:
                if message["typedAnnotations"][0]["text"] is not None:
                    message["content"] = message["typedAnnotations"][0]["text"]

    # pull the creator's display name if there is one, otherwise use their id for their "name"
    creatorName = ""
    creatorId = ""
    if "createdBy" in message and message["createdBy"] is not None:
        if "displayName" in message["createdBy"]:
            creatorName = message["createdBy"]["displayName"]
        if "id" in message["createdBy"]:
            creatorId = message["createdBy"]["id"]
    writer.writerow([message["id"], creatorName, creatorId, message["created"], message["content"]])

def get_messages_path(space_export_root, year, month):
    return space_export_root / str(year) / "messages {}.csv".format(month)

def find_messages_resume_point(space_export_root):
    ResumePoint = namedtuple('ResumePoint', ['last_time', 'last_id'])
    for year in range(datetime.datetime.now().year, 2014, -1):
        for month in range(12, 1, -1):
            path = get_messages_path(space_export_root, year, month)
            if path.exists():
                print("Found possible resume point in {}".format(path))
                with open(path, "r") as space_messages_file:
                    space_messages_reader = csv.reader(space_messages_file)
                    last_message_time = ""
                    for line in space_messages_reader:
                        if len(line) >= 4:
                            last_message_time = line[3]
                    if last_message_time:
                        try:
                            previous_time_in_milliseconds = int(parse(last_message_time).timestamp() * 1000)
                            print("Resuming from {} - aka {}".format(last_message_time, previous_time_in_milliseconds))
                            return ResumePoint(previous_time_in_milliseconds, line[0])
                        except ValueError:
                            pass
    return ResumePoint(None, None)

def export_space(space, auth_token, export_members, export_messages, export_root_folder=Path.home() / "Watson Workspace Export"):
    export_time = datetime.datetime.now()

    #if not export_root_folder:
    #    export_root_folder = Path.home() / "Watson Workspace Export" # PurePath() / "Watson Workspace Export"

    space_folder_name = "{} {}".format(space["title"].replace("/","-"), space["id"])
    space_export_root = export_root_folder / space_folder_name

    if not space_export_root.exists():
        space_export_root.mkdir(parents=True)

    print("Exporting to {}".format(space_export_root))

    # write members file
    if export_members:
        export_space_members(space["id"], space_export_root / "members {}.csv".format(export_time.strftime("%Y-%m-%d %H.%M")), auth_token)

    previous_time_in_milliseconds, last_known_id = find_messages_resume_point(space_export_root)
    previous_page_ids = []
    if last_known_id:
        previous_page_ids.append(last_known_id)

    # write message file
    # iterate over pages of messages for the space. We reverse them since they are in reverse chronological order
    # then, as we end a page, we note the timestamp to continue at for the next page

    try:
        space_messages_writer = None

        message = None
        message_count = 0

        # while there are no more pages of messages
        space_messages_file = None
        while export_messages:
            space_messages_page = requests.get_space_messages(space["id"], previous_time_in_milliseconds, auth_token)
            space_messages_page["items"].reverse()

            previous_message_year = ''
            previous_message_month = ''
            previous_time_in_milliseconds = ''

            page_ids = []
            found_new_message = False

            current_messages_path = None
            for message in space_messages_page["items"]:
                # if this message wasn't in the last page...
                if message["id"] not in previous_page_ids:
                    message_count += 1
                    found_new_message = True
                    page_ids.append(message["id"])

                    created_datetime = parse(message["created"])
                    previous_time_in_milliseconds = int(created_datetime.timestamp() * 1000)

                    # if necessary, tear down the old file and open a new one for the year and month of the next message
                    new_messages_path = get_messages_path(space_export_root, created_datetime.year, created_datetime.month)
                    if (new_messages_path != current_messages_path):
                        if space_messages_file and not space_messages_file.closed:
                            space_messages_file.flush()
                            space_messages_file.close()
                        if not new_messages_path.parent.exists():
                            new_messages_path.parent.mkdir(parents=True)

                        resuming_file = new_messages_path.exists()
                        space_messages_file = open(new_messages_path, "a")
                        current_messages_path = new_messages_path

                        space_messages_writer = csv.writer(space_messages_file)
                        if not resuming_file:
                            space_messages_writer.writerow(["message_id", "author name", "author id", "created date", "content"])

                    write_message(message, space_messages_writer)
            previous_page_ids = page_ids
            if not found_new_message:
                # There is potentially a case we could get here in error, if there were more messages with a specific timestamp
                # than our paging would allow - getting us stuck on the time. We could try to detect this, but it's probably not
                # going to happen with any space.
                if message:
                    print("Printed {} messages for space {}. The last known message was {} with content {}.".format(message_count, space["id"], message["id"], message["content"]))
                else:
                    print("Printed {} messages for space {}.".format(message_count, space["id"]))
                break

    finally:
        if space_messages_file is not None and not space_messages_file.closed:
            space_messages_file.flush()
            space_messages_file.close()
