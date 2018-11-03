import client

import logging
import os
import csv
import datetime
from pathlib import Path
from pathlib import PurePath
from dateutil.parser import parse
from collections import namedtuple

logger = logging.getLogger("wwexport")

messages_file_format = "messages {}.csv"

def get_all_spaces(auth_token:str) -> list:
    after = None
    all_spaces = []
    while True:
        spaces_page = client.get_spaces(after, auth_token)
        all_spaces.extend(spaces_page["items"])

        if (spaces_page["pageInfo"]["hasNextPage"]):
            after = spaces_page["pageInfo"]["endCursor"]
        else:
            break
    return all_spaces

def export_space_members(space_id:str, filename:str, auth_token:str) -> list:
    with open(filename,"w+") as space_members_file:
        space_members_writer = csv.writer(space_members_file)
        space_members = []
        after = None
        while True:
            space_members_page = client.get_space_members(space_id, after, auth_token)
            for member in space_members_page["items"]:
                space_members_writer.writerow([member["displayName"],member["email"],member["id"]])

            space_members.extend(space_members_page["items"])

            if (space_members_page["pageInfo"]["hasNextPage"]):
                after = space_members_page["pageInfo"]["endCursor"]
            else:
                break
        logger.info("Printed %s members", len(space_members))
    return space_members

def export_space_files(space_id:str, folder:PurePath, auth_token:str) -> int:
    count = 0
    after = None
    while True:
        space_files_page = client.get_space_files(space_id, after, auth_token)
        for file in space_files_page:
            client.download_file(file["id"], file["title"], folder, auth_token)

        if (space_files_page["pageInfo"]["hasNextPage"]):
            after = space_files_page["pageInfo"]["endCursor"]
        else:
            break
    logger.info("Exported %s files", count)
    return count

def write_message(message:str, writer:csv.DictWriter) -> None:
    # if there isn't content, pull it from the annotation if there is one
    if message["content"] is None:
        if message["typedAnnotations"] is not None and len(message["typedAnnotations"]) >0:
            if message["typedAnnotations"][0]["text"] is not None:
                logger.debug("Content is empty, but found an annotation with text on message %s", message["id"])
                message["content"] = message["typedAnnotations"][0]["text"]
            else:
                logger.warn("Content is empty and the first annotation didn't have text on message %s", message["id"])

    # pull the creator's display name if there is one, otherwise use their id for their "name"
    creatorName = None
    creatorId = None
    if "createdBy" in message and message["createdBy"] is not None:
        if "displayName" in message["createdBy"]:
            creatorName = message["createdBy"]["displayName"]
        if "id" in message["createdBy"]:
            creatorId = message["createdBy"]["id"]
    writer.writerow([message["id"], creatorName, creatorId, message["created"], message["content"]])

def get_messages_path(space_export_root:str, year:int, month:int) -> str:
    return space_export_root / str(year) / "messages {}.csv".format(month)

ResumePoint = namedtuple('ResumePoint', ['last_time', 'last_id'])
def find_messages_resume_point(space_export_root) -> ResumePoint:
    for year in range(datetime.datetime.now().year, 2014, -1):
        for month in range(12, 1, -1):
            path = get_messages_path(space_export_root, year, month)
            if path.exists():
                logger.debug("Found possible resume point in %s", path)
                with open(path, "r") as space_messages_file:
                    space_messages_reader = csv.reader(space_messages_file)
                    last_message_time = ""
                    for line in space_messages_reader:
                        if len(line) >= 4:
                            last_message_time = line[3]
                    if last_message_time:
                        try:
                            previous_time_in_milliseconds = int(parse(last_message_time).timestamp() * 1000)
                            return ResumePoint(previous_time_in_milliseconds, line[0])
                        except ValueError:
                            pass
    return ResumePoint(None, None)

def export_space(space:dict, auth_token:str, export_members:bool, export_messages:bool, export_files:bool, export_root_folder:PurePath=Path.home() / "Watson Workspace Export") -> None:
    export_time = datetime.datetime.now()

    space_folder_name = "{} {}".format(space["title"].replace("/","-"), space["id"])
    space_export_root = export_root_folder / space_folder_name
    space_export_root.mkdir(exist_ok=True, parents=True)

    logger.info(">>Exporting %s with ID %s to %s", space["title"], space["id"], space_export_root)

    if export_members:
        export_space_members(space["id"], space_export_root / "members {}.csv".format(export_time.strftime("%Y-%m-%d %H.%M")), auth_token)

    if export_files:
        files_folder_path = space_export_root / "files"
        files_folder_path.mkdir(exist_ok=True, parents=True)
        export_space_files(space["id"], files_folder_path, auth_token)

    next_page_time_in_milliseconds, last_known_id = find_messages_resume_point(space_export_root)
    previous_page_ids = []
    if last_known_id:
        logger.info("Resuming from message ID %s at %sms", last_known_id, next_page_time_in_milliseconds)
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
            space_messages_page = client.get_space_messages(space["id"], next_page_time_in_milliseconds, auth_token)
            logger.debug("Fetched page with %s items", len(space_messages_page))
            space_messages_page.reverse()

            page_ids = []
            found_new_message = False

            current_messages_path = None
            for message in space_messages_page:
                # If this message wasn't in the last page...
                # This check is necessary since we paginate by created time of
                # the message. Without this, we would either need to slightly
                # increment the time, and risk losing messages, or we would
                # print the same message twice
                if message["id"] not in previous_page_ids:
                    message_count += 1
                    found_new_message = True
                    page_ids.append(message["id"])

                    created_datetime = parse(message["created"])
                    next_page_time_in_milliseconds = int(created_datetime.timestamp() * 1000)

                    # If necessary, tear down the old file and open a new one
                    # for the year and month of the next message
                    new_messages_path = get_messages_path(space_export_root, created_datetime.year, created_datetime.month)
                    if (new_messages_path != current_messages_path):
                        if space_messages_file and not space_messages_file.closed:
                            logger.debug("Closing file while switching files")
                            space_messages_file.flush()
                            space_messages_file.close()

                        new_messages_path.parent.mkdir(exist_ok=True, parents=True)

                        resuming_file = new_messages_path.exists()
                        space_messages_file = open(new_messages_path, "a")
                        current_messages_path = new_messages_path

                        space_messages_writer = csv.writer(space_messages_file)
                        if not resuming_file:
                            logger.debug("Starting a new file. Writing header.")
                            space_messages_writer.writerow(["message_id", "author name", "author id", "created date", "content"])

                    write_message(message, space_messages_writer)
                else:
                    logger.debug("Skipping message with ID %s. This may just mean this message was on a prior page. This should normally happen exactly once per page, other than the first page, which it should not occur.", message["id"])
            previous_page_ids = page_ids
            if not found_new_message:
                # There is potentially a case we could get here in error, if
                # there were more messages with a specific timestamp than our
                # paging would allow - getting us stuck on the time. We could
                # try to detect this, but it's probably not going to happen with
                # any space.
                if message:
                    logger.info("Printed %s messages for space %s. The last known message was %s.", message_count, space["id"], message["id"])
                else:
                    logger.info("Printed %s messages for space %s.", message_count, space["id"])
                break

    finally:
        if space_messages_file is not None and not space_messages_file.closed:
            logger.debug("Closing file at end of space export")
            space_messages_file.flush()
            space_messages_file.close()
