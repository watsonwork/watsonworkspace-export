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

import argparse
import csv
import datetime
import dateutil
import dateutil.parser
import json
import logging
import markdown
import sys
from pathlib import Path
from functools import partial

from bleach.sanitizer import Cleaner
from bleach.linkifier import LinkifyFilter
from babel.dates import format_date, format_datetime, format_time
# force pyinstaller to find babel.numbers and include it
import babel.numbers

from jinja2 import Environment, FileSystemLoader
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.inlinepatterns import SimpleTagPattern
from markdown.util import etree

logger = logging.getLogger("wwexport")
paths = {}

cleaner = Cleaner(
    tags=["a", "br", "code", "em", "img", "p", "pre", "span", "strong"],
    attributes={"a": ["class", "href", "rel"], "img": ["alt", "src"]},
    styles=[],
    protocols=["file", "ftp", "ftps", "git", "http", "https", "ibmscp", "ldap", "ldaps", "mailto", "notes", "tel", "watsonworkspace"],
    strip=False,
    strip_comments=True,
    filters=[partial(LinkifyFilter, skip_tags=["code", "pre"])]
)

jinja_env = Environment(
    # use of the FileSystemLoader is required for PyInstaller packaging
    loader=FileSystemLoader(searchpath=str(Path(__file__).parent / "templates"))
)


def _jinja_filter_name_case(val: str):
    return val.title() if val is not None and (val.islower() or val.isupper()) else val

FILE_RE = r"<\$file\|(.*?)(\|(.*?))?>"
IMAGE_RE = r"<\$image\|(.*?)(\|(([0-9]+)x([0-9]+)))?>"
MENTION_RE = r"<@(.+?)\|(.+?)>"
SPACE_MENTION_RE = r"(<)(@space)>"
STRONG_RE = r"(\*)(.+?)\*"

class FilePattern(InlineProcessor):
    def handleMatch(self, m, data):
        global paths
        el = etree.Element("a")
        el.text = m.group(3)
        el.set("class", "ic-file")
        if m.group(1) in paths:
            el.set("href", paths[m.group(1)])
        else:
            el.set("href", "")
            logger.error("Could not resolve link in message to file for file %s", m.group(1))
        return el, m.start(0), m.end(0)

class ImagePattern(InlineProcessor):
    def handleMatch(self, m, data):
        global paths
        el = etree.Element("img")
        el.set("alt", "")
        # el.set("width", m.group(4))
        # el.set("height", m.group(5))
        if m.group(1) in paths:
            el.set("src", paths[m.group(1)])
        else:
            el.set("src", "")
            logger.error("Could not resolve link in message to image for image %s", m.group(1))
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


def csv_to_html(file: Path, styles: str = "styles.css"):
    logger.info("Converting %s to HTML", file)
    template = jinja_env.get_template("messages.html")
    file_paths_file_path = file.parent / "files" / constants.FILES_META_FOLDER / constants.FILE_PATHS_FILE_NAME

    global paths
    paths = {}
    if file_paths_file_path.exists():
        with open(file_paths_file_path, "r", encoding=constants.FILE_ENCODING) as paths_file:
            paths = json.load(paths_file)

    with open(file.with_suffix(".html"), "w+", encoding=constants.FILE_ENCODING) as html_file, \
         open(file, "r", encoding=constants.FILE_ENCODING) as csv_file:
        reader = csv.DictReader(csv_file)
        html_file.write(
            template.render(
                reader=reader,
                source_file=file.name,
                export_date=datetime.datetime.now(),
                styles=styles,
            )
        )


def main(argv):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Utility to convert from an exported CSV to HTML file")

    parser.add_argument("--file", help="Path to messages CSV file previously generated by the export tool.")
    args = parser.parse_args()

    csv_to_html(Path(args.file))


if __name__ == "__main__":
    main(sys.argv)
