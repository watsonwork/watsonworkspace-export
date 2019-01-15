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

from wwexport import constants

import argparse
import csv
import datetime
import dateutil
import dateutil.parser
import json
import logging
import os
import re
import sys
from pathlib import Path
from functools import partial

from bleach.sanitizer import Cleaner
from bleach.linkifier import LinkifyFilter
from mistletoe import Document, html_renderer
from mistletoe.span_token import SpanToken
from babel.dates import format_date, format_datetime, format_time

from jinja2 import Environment, PackageLoader, select_autoescape

logger = logging.getLogger("wwexport")
paths = {}
cleaner = Cleaner(
    tags=['a', 'code', 'em', 'img', 'p', 'pre', 'span', 'strong'],
    attributes={'a': ['class', 'href', 'rel'], 'img': ['src']},
    styles=[],
    protocols=['file', 'ftp', 'ftps', 'git', 'http', 'https', 'ibmscp', 'ldap', 'ldaps', 'mailto', 'notes', 'tel', 'watsonworkspace'],
    strip=False,
    strip_comments=True,
    filters=[partial(LinkifyFilter, skip_tags=['code', 'pre'])]
)

class WWMentionSpan(SpanToken):
    pattern = re.compile(r"\<\@(.+?)\|(.+?)\>")

    def __init__(self, match):
        self.parse_inner = False
        self.id = match.group(1)
        self.display = match.group(2)

class WWSpaceMentionSpan(SpanToken):
    pattern = re.compile(r"\<(\@space)\>")

    def __init__(self, match):
        self.parse_inner = False
        self.display = match.group(1)

class WWFileSpan(SpanToken):
    pattern = re.compile(r"\<\$file\|(.+)\|(.*)\>")

    def __init__(self, match):
        global paths
        self.parse_inner = False
        self.path = paths[match.group(1)]
        self.name = match.group(2)

class WWImageSpan(SpanToken):
    pattern = re.compile(r"\<\$image\|(.*?)(\|(([0-9])+x([0-9])+))?\>")

    def __init__(self, match):
        global paths
        self.parse_inner = False
        self.path = paths[match.group(1)]
        self.width = match.group(4)
        self.height = match.group(5)

class WWBoldSpan(SpanToken):
    pattern = re.compile(r"\*([^*]+)\*")

    def __init__(self, match):
        self.target = match.group(1)

class WWHTMLRenderer(html_renderer.HTMLRenderer):
    def __init__(self):
        super().__init__(WWMentionSpan, WWSpaceMentionSpan, WWFileSpan, WWImageSpan, WWBoldSpan)

    def render_ww_mention_span(self, token):
        return "<strong>{name}</strong>".format(name=token.display)

    def render_ww_space_mention_span(self, token):
        return self.render_ww_mention_span(token)

    def render_ww_file_span(self, token):
        return "<a class=\"ic-file\" href=\"{path}\">{name}</a>".format(name=token.name, path=token.path)

    def render_ww_image_span(self, token):
        return "<img src=\"{path}\" alt />".format(path=token.path)

    def render_ww_bold_span(self, token):
        return "<strong>{inner}</strong>".format(inner=self.render_inner(token))


jinja_env = Environment(
    loader=PackageLoader('wwexport', 'templates'),
    autoescape=select_autoescape(['html', 'xml'])
)


def _jinja_filter_name_case(val: str):
    return val.title() if val is not None and (val.islower() or val.isupper()) else val


def _jinja_filter_md(val: str):
    with WWHTMLRenderer() as renderer:
        return cleaner.clean(
            renderer.render(
                Document(val)
            )
        )


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
                month_year="201811",
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
