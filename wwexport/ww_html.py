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

from wwexport import constants
from wwexport import env

import argparse
import csv
import datetime
import dateutil
import dateutil.parser
import json
import logging
import markdown
import sys
import fnmatch
import pkgutil
import hashlib
from pathlib import Path
from functools import partial
from collections.abc import Iterator

from bleach.sanitizer import Cleaner
from bleach.linkifier import LinkifyFilter
from babel.dates import format_date, format_datetime, format_time
# force pyinstaller to find babel.numbers and include it
import babel.numbers

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.inlinepatterns import SimpleTagPattern
from markdown.util import etree

logger = logging.getLogger("wwexport")
paths = {}

cleaner = Cleaner(
    tags=["a", "br", "code", "em", "img", "p", "pre", "span", "strong"],
    attributes={"a": ["class", "href", "rel"], "code": ["class"], "img": ["alt", "src"]},
    styles=[],
    protocols=["file", "ftp", "ftps", "git", "http", "https", "ibmscp", "ldap", "ldaps", "mailto", "notes", "tel", "watsonworkspace"],
    strip=False,
    strip_comments=True,
    filters=[partial(LinkifyFilter, skip_tags=["code", "pre"])]
)

jinja_env = Environment(
    # use of the FileSystemLoader is required for PyInstaller packaging
    loader=FileSystemLoader(searchpath=str(Path(__file__).parent / "templates")),
    autoescape=select_autoescape(['html', 'xml']),
    extensions=["jinja2.ext.do"],
    trim_blocks=True,
    lstrip_blocks=True,
)


def _jinja_filter_name_case(val: str):
    return val.title() if val is not None and (val.islower() or val.isupper()) else val

FILE_RE = r"<\$file\|(.*?)(\|(.*?))?>"
IMAGE_RE = r"<\$image\|(.*?)(\|(([0-9]+)x([0-9]+)))?>"
MENTION_RE = r"<@(.+?)\|(.+?)>"
SPACE_MENTION_RE = r"(<)(@space)>"
STRONG_RE = r"(\*)(.+?)\*"

def file_path_for_id(id):
    if id in paths:
        return "file://" + paths[id]
    else:
        try:
            short_id = id.split("@")[-1]
            if short_id in paths:
                return "file://" + paths[short_id]
        except IndexError:
            logger.error("Could not resolve link in message to file %s, ID is an unexpected format", id)

        logger.error("Could not resolve link in message to file %s", id)
        return ""

class FilePattern(InlineProcessor):
    def handleMatch(self, m, data):
        el = etree.Element("a")
        el.text = m.group(3)
        el.set("class", "ic-file")
        el.set("href", file_path_for_id(m.group(1)))
        return el, m.start(0), m.end(0)

class ImagePattern(InlineProcessor):
    def handleMatch(self, m, data):
        el = etree.Element("img")
        el.set("alt", "")
        # el.set("width", m.group(4))
        # el.set("height", m.group(5))
        el.set("src", file_path_for_id(m.group(1)))
        return el, m.start(0), m.end(0)

class WWExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        md.inlinePatterns["strong"] = SimpleTagPattern(STRONG_RE, "strong")

        md.inlinePatterns.add("file", FilePattern(FILE_RE), ">emphasis2")
        md.inlinePatterns.add("image", ImagePattern(IMAGE_RE), ">emphasis2")
        md.inlinePatterns.add("mention", SimpleTagPattern(MENTION_RE, "strong"), ">emphasis2")
        md.inlinePatterns.add("space_mention", SimpleTagPattern(SPACE_MENTION_RE, "strong"), ">emphasis2")

        del md.preprocessors["html_block"]
        del md.preprocessors["reference"]

        del md.inlinePatterns["autolink"]
        del md.inlinePatterns["automail"]
        del md.inlinePatterns["em_strong"]
        del md.inlinePatterns["entity"]
        del md.inlinePatterns["html"]
        del md.inlinePatterns["image_link"]
        del md.inlinePatterns["image_reference"]
        del md.inlinePatterns["reference"]
        del md.inlinePatterns["short_reference"]
        del md.inlinePatterns["strong_em"]

        del md.parser.blockprocessors["code"] # `code` is an indented code block, WW only supports 'fenced' code blocks (using ```\nbackticks\n```)
        del md.parser.blockprocessors["hashheader"]
        del md.parser.blockprocessors["hr"]
        del md.parser.blockprocessors["indent"]
        del md.parser.blockprocessors["olist"]
        del md.parser.blockprocessors["quote"]
        del md.parser.blockprocessors["setextheader"]
        del md.parser.blockprocessors["ulist"]


markdownRenderer = markdown.Markdown(extensions=[WWExtension(), "markdown.extensions.fenced_code", "markdown.extensions.nl2br"], output_format="html5")

def _jinja_filter_md(val: str):
    content = None
    try:
        content = markdownRenderer.reset().convert(val)
        # ensure only expected tags are output, convert bare URLs (with allowed protocols) to links
        content = cleaner.clean(content)
    except NameError:
        logger.exception("Problem with markdown conversion - using message as plaintext for some message content")
        content = val
    except ValueError:
        logger.exception("Problem with markdown conversion - using message as plaintext for some message content")
        content = val

    return content


jinja_env.filters["format_date"] = format_date
jinja_env.filters["format_datetime"] = format_datetime
jinja_env.filters["format_time"] = format_time
jinja_env.filters["parse_datetime"] = dateutil.parser.parse
jinja_env.filters["name_case"] = _jinja_filter_name_case
jinja_env.filters["md"] = _jinja_filter_md


def create_styles():
    """Create a local copy of the styles file using a name based on hash
    so the HTML and CSS can be updated and an export resumed without breaking
    previous exports"""
    styles = pkgutil.get_data("wwexport", "resources/styles.css")
    m = hashlib.md5()
    m.update(styles)
    md5 = m.hexdigest()
    styles_destination = "styles_{}.css".format(md5)
    path = env.export_root / styles_destination
    if not path.exists():
        with open(path, "wb") as export_styles:
            export_styles.write(styles)
    return styles_destination


def is_message_file(path: Path) -> bool:
    return fnmatch.fnmatch(path.name, "* messages.csv")


class MultiFileDictReader(Iterator):

    def __init__(self, space_root: str):
        self.space_root = space_root
        self.current_reader = None
        self.curent_file = None
        self.marker = datetime.date(2014, 1, 1)
        self.done = False

    def __iter__(self):
        return self

    def __advance_month(self):
        logger.debug("About to advance month from %s", self.marker)
        self.marker = self.marker + dateutil.relativedelta.relativedelta(months=+1)
        if self.marker.year > datetime.datetime.now().year:
            self.done = True

    def get_reader(self):
        return self

    def __next__(self):
        if self.done:
            raise StopIteration

        while self.current_reader is None:
            # the current month's reader hasn't been opened yet,
            # or the file doesn't
            next_path = env.get_messages_path(self.space_root, self.marker.year, self.marker.month)
            if next_path.exists():
                # the current month's file exists, let's try to set up the reader
                self.current_file = open(next_path, "r", encoding=constants.FILE_ENCODING)
                self.current_reader = csv.DictReader(self.current_file)
            else:
                # the current month's file doesn't exist, advance and recurse
                self.__advance_month()
                return self.__next__()

        try:
            return self.current_reader.__next__()
        except StopIteration:
            # current reader is at end, close it out, advance the month and
            # recurse
            self.current_file.__exit__()
            self.current_reader = None
            self.__advance_month()
            return self.__next__()

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.current_file.__exit__(type, value, traceback)


def space_to_htmls(space_root, display_name):
    html_gen_errors = []
    styles = create_styles()
    for file in env.progress_bar(
            filter(is_message_file,
                   space_root.iterdir()
                   ),
            desc="HTML generation".format(display_name),
            position=1,
            unit=" HTML files",
            initial=1):
        try:
            csv_to_html(file, styles=styles)
        except Exception:
            html_gen_errors.append(file)
            logger.exception("An error occured while generating HTML for %s", file)
    return html_gen_errors


def space_to_single_html(space_root: Path):
    styles = create_styles()

    template = jinja_env.get_template("messages.html")
    file_paths_file_path = space_root / "files" / constants.FILES_META_FOLDER / constants.FILE_PATHS_FILE_NAME

    global paths
    paths = {}
    if file_paths_file_path.exists():
        with open(file_paths_file_path, "r", encoding=constants.FILE_ENCODING) as paths_file:
            paths = json.load(paths_file)
            # Some early file references use a slightly different prefix on the
            # ID compared to the ID reported by the file service. This change,
            # together with a change to the lookup code, will address that by
            # allowing the path to be checked against only the last segment of
            # the ID
            paths = {id.split("@")[-1]: path for (id, path) in paths.items()}

    with open(space_root / "all messages.html", "w+", encoding=constants.FILE_ENCODING) as html_file:
        reader = MultiFileDictReader(space_root)
        html_file.write(
            template.render(
                reader=reader,
                export_date=datetime.datetime.now(),
                styles=styles,
            )
        )


def csv_to_html(file: Path, styles: str = "styles.css"):
    logger.info("Converting %s to HTML", file)
    template = jinja_env.get_template("messages.html")
    file_paths_file_path = file.parent / "files" / constants.FILES_META_FOLDER / constants.FILE_PATHS_FILE_NAME

    global paths
    paths = {}
    if file_paths_file_path.exists():
        with open(file_paths_file_path, "r", encoding=constants.FILE_ENCODING) as paths_file:
            paths = json.load(paths_file)
            # Some early file references use a slightly different prefix on the
            # ID compared to the ID reported by the file service. This change,
            # together with a change to the lookup code, will address that by
            # allowing the path to be checked against only the last segment of
            # the ID
            paths = {id.split("@")[-1]: path for (id, path) in paths.items()}

    with open(file.with_suffix(".html"), "w+", encoding=constants.FILE_ENCODING) as html_file, \
         open(file, "r", encoding=constants.FILE_ENCODING) as csv_file:
        reader = csv.DictReader(csv_file)
        html_file.write(
            template.render(
                reader=reader,
                export_date=datetime.datetime.now(),
                styles=styles,
            )
        )


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Utility to convert from an exported CSV to HTML file")

    env.add_export_root_args(parser)
    parser.add_argument("--path", help="Path to messages CSV file previously generated by the export tool or, if a dir, this is interpreted as a space directory")
    parser.add_argument("--onefile", action="store_true", help="If specified, and if the path points to a space, only 1 (potentially very large) HTML file will be generated for the space. Use with caution.")
    env.add_logger_args(parser)
    args = parser.parse_args()

    env.config_export_root(args)
    env.config_logger(args)

    path = Path(args.path)
    if path.exists():
        create_styles()
        if path.is_dir():
            logger.info("Generating HTML for %s as a space root directory", path)
            if args.onefile:
                logger.info("Using the single file option for space HTML generation")
                space_to_single_html(path)
            else:
                space_to_htmls(path, str(path))
        else:
            logger.info("Generating HTML for %s as a message CSV", path)
            csv_to_html(path)
    else:
        logger.error("Path %s does not exist", path)


if __name__ == "__main__":
    main(sys.argv)
