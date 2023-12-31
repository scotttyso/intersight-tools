"""Intersight Formatting Helpers
This script provides formatting helper functions for use with the intersight python sdk
The following pip packages are required:
    - tabulate
"""
#=============================================================================
# Source Modules
#=============================================================================
def prRed(skk): print("\033[91m {}\033[00m" .format(skk))
import sys
try: from tabulate import tabulate
except ImportError as e:
    prRed(f'!!! ERROR !!!\n{e.__class__.__name__}')
    prRed(f" Module {e.name} is required to run this script")
    prRed(f" Install the module using the following: `pip install {e.name}`")
    sys.exit(1)

# Takes date object and returns formatted date string for use with intersight queries
def format_time(dt):
    s = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return f"{s[:-3]}Z"

# Takes an array of results and creates a formatted table output (assumes all entries have the same keys)
def print_results_to_table(obj, ignored_fields=[]):
    headers = []
    if 'intersight' in str(type(obj[0])):
        headers = [ k for k in obj[0].to_dict().keys() if k not in ignored_fields ]
    else:
        headers = [ k for k in obj[0].keys() if k not in ignored_fields ]
    entries = []
    for entry in obj:
        row = []
        for h in headers:
            row.append(entry.get(h))
        entries.append(row)
    print(tabulate(entries, headers=headers, tablefmt='orgtbl'))