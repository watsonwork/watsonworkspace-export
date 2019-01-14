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

import logging
import datetime
import re
import sys
import argparse
import dateutil
from pathlib import Path
from functools import partial

from bleach.sanitizer import Cleaner
from bleach.linkifier import LinkifyFilter
from mistletoe import Document, html_renderer
from mistletoe.span_token import SpanToken
import pandas as pd
from babel.dates import format_date, format_datetime, format_time

from jinja2 import Environment, PackageLoader, select_autoescape

logger = logging.getLogger("wwexport")

cleaner = Cleaner(
    tags=['a', 'code', 'em', 'img', 'p', 'pre', 'span', 'strong'],
    attributes={'a': ['href', 'rel'], 'img': ['src']},
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
    pattern = re.compile(r"\<\$file\|.+\|(.*)\>")

    def __init__(self, match):
        self.parse_inner = False
        self.name = match.group(1)

class WWImageSpan(SpanToken):
    pattern = re.compile(r"\<\$image\|(.*?)(\|(([0-9])+x([0-9])+))?\>")

    def __init__(self, match):
        self.parse_inner = False
        self.id = match.group(1)
        self.size = match.group(3)
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
        return "<a href=\"./files/{target}\">{target}</a>".format(target=token.name)

    def render_ww_image_span(self, token):
        return "<img alt='Embedded Image' href='{target}'/>".format(target=token.id)

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
    df = pd.read_csv(file, encoding=constants.FILE_ENCODING)
    template = jinja_env.get_template("messages.html")
    with open(file.with_suffix(".html"), "w+") as html_file:
        html_file.write(
            template.render(
                df=df,
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
