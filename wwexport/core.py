# MIT License
#
# Copyright 2018-2019 IBM
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

from wwexport import queries
from wwexport import auth
from wwexport import constants
from wwexport import env

import logging
import csv
import datetime
import json
from pathlib import Path
from pathlib import PurePath
from dateutil.parser import parse
from collections import namedtuple
from enum import Enum

logger = logging.getLogger("wwexport")
__current_user = None


class FileOptions(Enum):
    none = "NONE"
    resume = "RESUME"
    all = "ALL"

    def __str__(self):
        return self.value


ResumePoint = namedtuple('ResumePoint', ['last_time', 'last_id'])


def export_space_members(space_id: str, space_display_name: str, filename: str, auth_token: auth.AuthToken) -> list:
    with open(filename, "w+", newline='', encoding=constants.FILE_ENCODING) as space_members_file:
        space_members_writer = csv.writer(space_members_file)
        space_members = []
        after = None
        space_members_writer.writerow(["name", "email", "id"])
        with env.progress_bar(desc="Getting members",
                              position=1,
                              unit=" member batch",
                              initial=1) as member_progress:
            while True:
                space_members_page = queries.space_members.execute(auth_token, spaceid=space_id, after=after)
                for member in space_members_page["items"]:
                    space_members_writer.writerow(
                        [member["displayName"], member["email"], member["id"]])

                space_members.extend(space_members_page["items"])

                if (space_members_page["pageInfo"]["hasNextPage"]):
                    after = space_members_page["pageInfo"]["endCursor"]
                else:
                    break
                member_progress.clear()
                member_progress.update()

        logger.info("Printed %s members to %s", len(space_members), filename)
    return space_members


def new_export_space_files(space_id: str, folder: PurePath, auth_token: str) -> int:
    return 0


def export_space_files(space_id: str, folder: PurePath, auth_token: str, fetch_after_timestamp: int = 0) -> int:
    """Export spaces, starting with the newest and going back only to the
    fetch_after_timestamp. This order is implemented since paging from oldest
    to newest doesn't seem to be implemented for the beta resource API.
    The downside to this approach is that if file name collisions occurs,
    the names will be non-deterministic and depend on when the files are created
    relative to prior executions of this method. For instance, myfile.txt and
    myfile 1.txt will refer to two files with title myfile.txt. Because we
    start from newest to oldest, myfile.txt will normally be the newest file,
    and myfile 1.txt will be older. This may already be counter-intuitive, but
    additionally, if the task was already run and an earlier file was downloaded
    as myfile.txt, it's possible the newer file will be named myfile 1.txt"""

    if fetch_after_timestamp:
        logger.info("Exporting files only back to %s ms", fetch_after_timestamp)

    file_graphqlitem_by_id = {}
    file_entries_file_path = folder / constants.FILES_META_FOLDER / constants.FILE_ENTRIES_FILE_NAME
    if (file_entries_file_path).exists():
        with open(file_entries_file_path, "r", encoding=constants.FILE_ENCODING) as f:
            file_graphqlitem_by_id = json.load(f)
    file_path_by_id = {}
    file_paths_file_path = folder / constants.FILES_META_FOLDER / constants.FILE_PATHS_FILE_NAME
    if (file_paths_file_path).exists():
        with open(file_paths_file_path, "r", encoding=constants.FILE_ENCODING) as f:
            file_path_by_id = json.load(f)

    downloaded = 0
    already_downloaded = 0
    duplicates = 0

    try:
        previous_page_ids = set()
        next_page_time_in_milliseconds = None

        with env.progress_bar(desc="Downloading files",
                              position=1,
                              unit=" files",
                              initial=1) as file_progress:
            while True:
                space_files_page = queries.space_files.execute(auth_token, spaceid=space_id, timestamp=next_page_time_in_milliseconds)
                if space_files_page:
                    logger.debug("Fetched page with %s files for space %s", len(
                        space_files_page), space_id)
                elif len(previous_page_ids) == 0:
                    logger.debug("No files found for space %s", space_id)
                    break
                else:
                    logger.error(
                        "Fetched page with no files for space %s, but expected this page to contain at least one file.")
                    break

                folder.mkdir(exist_ok=True, parents=True)

                found_file = False
                page_ids = set()
                for file in space_files_page:
                    file_progress.update()
                    file_created_ms = int(
                        parse(file["created"]).timestamp() * 1000)
                    if file_created_ms >= fetch_after_timestamp:
                        file_graphqlitem_by_id[file["id"]] = file
                        if file["id"] in previous_page_ids:
                            logger.debug(
                                "skipping file with id %s since it was in the last page", file["id"])
                        else:
                            found_file = True
                            page_ids.add(file["id"])
                            if next_page_time_in_milliseconds:
                                next_page_time_in_milliseconds = min(
                                    next_page_time_in_milliseconds, file_created_ms)
                            else:
                                next_page_time_in_milliseconds = file_created_ms
                            if file["id"] in file_path_by_id and Path(file_path_by_id[file["id"]]).exists():
                                logger.debug(
                                    "file %s is already downloaded to %s, skipping download", file["id"], file_path_by_id[file["id"]])
                                already_downloaded += 1
                            else:
                                file_path, new_file = queries.download(
                                    file["id"], file["title"], folder, auth_token)
                                if file_path:
                                    file_path_by_id[file["id"]] = str(file_path)
                                if new_file:
                                    downloaded += 1
                                else:
                                    duplicates += 1
                    else:
                        logger.debug(
                            "ignoring file %s since it is before the requested resume point %s", file["id"], fetch_after_timestamp)

                previous_page_ids = page_ids
                if not found_file:
                    break

    finally:
        # if we have some metadata, write it
        if len(file_graphqlitem_by_id) > 0:
            file_entries_file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(file_entries_file_path, "w+", encoding=constants.FILE_ENCODING) as f:
                json.dump(file_graphqlitem_by_id, f)
        if len(file_path_by_id) > 0:
            file_paths_file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(file_paths_file_path, "w+", encoding=constants.FILE_ENCODING) as f:
                json.dump(file_path_by_id, f)

    logger.info("Downloaded %s files, %s files were skipped because they were downloaded according to meta files, %s downloaded files were duplicates of files already downloaded",
                downloaded, already_downloaded, duplicates)
    return downloaded


def write_message_to_csv(message: str, writer: csv.DictWriter) -> None:
    annotations = None
    annotationActor = None
    annotationTitle = None
    annotationColor = None

    # if there isn't content, pull it from the annotation if there is one
    if message["content"] is None:
        if message["typedAnnotations"] is not None and len(message["typedAnnotations"]) > 0:
            typedAnnotation = message["typedAnnotations"][0]
            if typedAnnotation is not None and "text" in typedAnnotation and typedAnnotation["text"] is not None:
                logger.debug(
                    "Content is empty, but found an annotation with text on message %s", message["id"])
                message["content"] = typedAnnotation["text"] or " "
                annotationActor = typedAnnotation["actor"]["name"]
                annotationTitle = typedAnnotation["title"]
                annotationColor = typedAnnotation["color"]
            else:
                logger.warn(
                    "Content is empty and the first annotation didn't have text on message %s", message["id"])

    # pull the creator's display name if there is one, otherwise use their id for their "name"
    creatorName = None
    creatorId = None
    if "createdBy" in message and message["createdBy"] is not None:
        if "displayName" in message["createdBy"]:
            creatorName = message["createdBy"]["displayName"]
        if "id" in message["createdBy"]:
            creatorId = message["createdBy"]["id"]
    if "annotations" in message:
        annotations = message["annotations"]

    writer.writerow([message["id"], creatorName, creatorId,
                    message["created"], message["content"],
                    annotations, annotationActor,
                    annotationTitle, annotationColor])


def get_messages_path(space_export_root: str, year: int, month: int) -> str:
    return space_export_root / constants.MESSAGES_FILE_NAME_PATTERN.format(year=year, month=month)


def find_messages_resume_point(space_export_root) -> ResumePoint:
    for year in range(datetime.datetime.now().year, 2013, -1):
        for month in range(12, 0, -1):
            path = get_messages_path(space_export_root, year, month)
            if path.exists():
                logger.debug("Found possible resume point in %s", path)
                with open(path, "r", newline='', encoding=constants.FILE_ENCODING) as space_messages_file:
                    space_messages_reader = csv.reader(space_messages_file)
                    last_message_time = None
                    for line in space_messages_reader:
                        if len(line) >= 4:
                            last_message_time = line[3]
                        else:
                            logger.warn(
                                "Found a line shorter than expected in %s when looking for resume point. You may want to delete (or move) this space's local messages and try again.", path)
                    if last_message_time:
                        try:
                            previous_time_in_milliseconds = int(
                                parse(last_message_time).timestamp() * 1000)
                            return ResumePoint(previous_time_in_milliseconds, line[0])
                        except ValueError:
                            pass
    return ResumePoint(0, None)


def get_DM_participant(space: dict, auth_token: str) -> dict:
    global __current_user
    dm_participant = None
    if "members" in space and "items" in space["members"]:
        if not __current_user:
            __current_user = queries.current_user.execute(auth_token)
        other_participants = [member for member in space["members"]["items"] if member["id"] != __current_user["id"]]
        if len(other_participants) == 1:
            dm_participant = other_participants[0]
        else:
            logger.error("%s looked like a direct messaging space, but it has %s participants other than yourself", space["id"], len(other_participants))
    else:
        logger.error("%s looked like a direct messaging space, but we didn't get any members for it", space["id"])
    return dm_participant


def space_pathsafe_name(space: dict, auth_token: str):
    name = space["id"]
    if space["type"] == "DIRECT":
        other_participant = get_DM_participant(space, auth_token)
        if other_participant:
            name = "{} - {}".format(other_participant["displayName"], other_participant["email"])
        else:
            name = space["id"]
            logger.error("space with id %s at %s like a direct messaging space, but we didn't find another member in it - we'll generate the display name based on the user ID", space["id"], name)
    else:
        if space["type"] != "TEAM":
            logger.warn("space with id %s has type %s - neither TEAM nor DIRECT (DM) - will treat the space as a team space", space["id"], space["type"])
        if space["title"]:
            name = "{} {}".format(space["title"], space["id"])
        else:
            name = space["id"]
            logger.warn("space with id %s at %s lacks a title", space["id"], name)
    if name:
        name = name.translate(constants.FILE_NAME_TRANSLATION_TABLE)
    return name


def get_space_folder(space_type: str, space_display_name: str, root_path: PurePath, auth_token: str):
    type_folder = "DM" if space_type == "DIRECT" else "SPACE"
    return root_path / type_folder / space_display_name


def export_space(space: dict, auth_token: str, export_root_folder: PurePath, file_options: FileOptions = FileOptions.none, export_members: bool = True, export_messages: bool = True, export_annotations: bool = False, space_progress=False) -> (Path, str):
    export_time = datetime.datetime.now()

    space_display_name = space_pathsafe_name(space, auth_token)
    space_progress.set_description(space_display_name[0:15] + "...")

    space_export_root = get_space_folder(space["type"], space_display_name, export_root_folder, auth_token)
    space_export_root.mkdir(exist_ok=True, parents=True)

    logger.info(">> Exporting space %s to %s", space_display_name, space_export_root)

    if export_members:
        export_space_members(space["id"], space_display_name, space_export_root / "members {}.csv".format(
            export_time.strftime("%Y-%m-%d %H.%M")), auth_token)

    next_page_time_in_milliseconds, last_known_id = find_messages_resume_point(
        space_export_root)
    previous_page_ids = set()
    if last_known_id:
        logger.info("Resuming from message ID %s at %sms",
                    last_known_id, next_page_time_in_milliseconds)
        previous_page_ids.add(last_known_id)
    else:
        logger.info("Resume point not found")

    if file_options != FileOptions.none:
        files_folder_path = space_export_root / "files"
        if file_options == FileOptions.all:
            export_space_files(space["id"], files_folder_path, auth_token)
        elif file_options == FileOptions.resume:
            export_space_files(
                space["id"], files_folder_path, auth_token, next_page_time_in_milliseconds)
        else:
            logger.warn("Unsupported file option")

    # write message file
    # iterate over pages of messages for the space. We reverse them since they are in reverse chronological order
    # then, as we end a page, we note the timestamp to continue at for the next page

    try:
        space_messages_writer = None

        message = None
        message_count = 0

        # while there are no more pages of messages
        space_messages_file = None
        message_query = queries.space_messages_with_annotations if export_annotations else queries.space_messages
        with env.progress_bar(desc="Downloading messages",
                              position=1,
                              unit=" message batch",
                              initial=1) as message_progress:
            while export_messages or export_annotations:
                space_messages_page = message_query.execute(auth_token, spaceid=space["id"], oldest=next_page_time_in_milliseconds)
                if not space_messages_page:
                    if message_count == 0:
                        if last_known_id:
                            logger.warn(
                                "Fetched a page with no messages for space %s, but expected at least message %s. This may be OK if the space has no new messages and this message was deleted", space["id"], last_known_id)
                        else:
                            logger.info(
                                "Fetched empty page of messages and was not resuming. Looks like space %s has no messages", space["id"])
                    else:
                        logger.error(
                            "Fetched a page with no messages, but had printed previous pages. Expected at least one message on this page")
                    break

                logger.debug("Fetched page with %s messages",
                             len(space_messages_page))
                space_messages_page.reverse()

                page_ids = set()
                found_new_message = False

                current_messages_path = None
                for message in space_messages_page:
                    # If this message wasn't in the last page...
                    # This check is necessary since we paginate by created time of
                    # the message. Without this, we would either need to slightly
                    # increment the time, and risk losing messages, or we would
                    # print the same message twice. Why not compare just the last
                    # ID? If there is more than 1 message at this time, then there
                    # could be multiple messages overlapping. In the extreme case,
                    # an entire page overlaps and the script exits thinking it
                    # didn't find new messages, but this is extremely unlikely
                    if message["id"] not in previous_page_ids:
                        message_count += 1
                        found_new_message = True
                        page_ids.add(message["id"])

                        created_datetime = parse(message["created"])
                        next_page_time_in_milliseconds = int(
                            created_datetime.timestamp() * 1000)

                        # If necessary, tear down the old file and open a new one
                        # for the year and month of the next message
                        new_messages_path = get_messages_path(
                            space_export_root, created_datetime.year, created_datetime.month)
                        if (new_messages_path != current_messages_path):
                            if space_messages_file and not space_messages_file.closed:
                                logger.debug("Closing file while switching files")
                                space_messages_file.flush()
                                space_messages_file.close()

                            new_messages_path.parent.mkdir(
                                exist_ok=True, parents=True)

                            resuming_file = new_messages_path.exists()
                            space_messages_file = open(new_messages_path, "a", newline='', encoding=constants.FILE_ENCODING)
                            current_messages_path = new_messages_path

                            space_messages_writer = csv.writer(space_messages_file)
                            if not resuming_file:
                                logger.debug(
                                    "Starting a new file. Writing header.")
                                space_messages_writer.writerow(
                                    ["message id", "author name", "author id", "created date", "content", "annotations",
                                     "annotationActor", "annotationTitle", "annotationColor"])

                        write_message_to_csv(message, space_messages_writer)
                    else:
                        logger.debug(
                            "Skipping message with ID %s. This may just mean this message was on a prior page. This should normally happen exactly once per page, other than the first page, which it should not occur.", message["id"])
                previous_page_ids = page_ids
                if not found_new_message:
                    # There is potentially a case we could get here in error, if
                    # there were more messages with a specific timestamp than our
                    # paging would allow - getting us stuck on the time. We could
                    # try to detect this, but it's probably not going to happen with
                    # any space.
                    if message:
                        logger.info("Printed %s messages for space %s. The last known message was %s.",
                                    message_count, space["id"], message["id"])
                    else:
                        logger.info("Printed %s messages for space %s.",
                                    message_count, space["id"])
                    break
                message_progress.update()

    finally:
        if space_messages_file is not None and not space_messages_file.closed:
            logger.debug("Closing file at end of space export")
            space_messages_file.flush()
            space_messages_file.close()

    return space_export_root, space_display_name
