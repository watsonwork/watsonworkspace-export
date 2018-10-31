#!/usr/bin/env python

import exporter.core
import sys

auth_token=sys.argv[1]

if not auth_token:
    auth_token = exporter.core.get_auth_token()

spaces = exporter.core.get_all_spaces(auth_token)

for space in spaces:
    exporter.core.export_space(space, auth_token, True, True)

print("done!")
