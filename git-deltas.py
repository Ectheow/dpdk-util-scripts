#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import re
import collections

UPSTREAM_COMPLIANT_PATTERN=re.compile(r'^upstream/[\d\.]+$')
UPSTREAM_GIT_PATTERN='upstream'
UPSTREAM_OVERRIDE_PATTERN=re.compile(r'^(upstream/[\d\.]+)\-real$')


TagScheme = collections.namedtuple('TagScheme', ['prefix', 'check_pattern', 'override_pattern'])
UPSTREAM_TAG_SCHEME = TagScheme(
    UPSTREAM_GIT_PATTERN,
    UPSTREAM_COMPLIANT_PATTERN,
    UPSTREAM_OVERRIDE_PATTERN)

FORMATS = {
    "html":{
        "para_begin":"<p>",
        "para_end":"<p>",
        "table_begin":"<table>",
        "table_end":"</table>",
        "column_begin":"<td>",
        "column_end":"</td>",
        "row_begin":"<tr>",
        "row_end":"</tr>",
    },
    "text":{
        "para_begin":"\n",
        "para_end":"\n",
        "table_begin":"",
        "table_end":"",
        "column_begin":"    ",
        "column_end":"",
        "row_begin":"",
        "row_end":""
    }
}

class Formatter:
    def __init__(self, table):
        self.table = table
    def out(self, name):
        if self.table[name] != None and \
            self.table[name] != "" and \
            (name in self.table):

            print(self.table[name], end='')

def lines_in_command(shell_command):
    shell = True
    if type(shell_command) == list:
        shell = False

    proc = subprocess.Popen(shell_command, shell=shell, stdout=subprocess.PIPE)
    for line in  iter(proc.stdout.readline, b''):
        yield line.decode('ASCII').strip()


def git_ordered_tags(pattern):
    return list(
        map(lambda s: s.strip(),
            sorted(lines_in_command("git tag --list {}".format(pattern)), reverse=True)))


def git_checked_tag_list(scheme):
    tags = []
    overrides= {}
    errors = []
    for tag in git_ordered_tags("{}/*".format(scheme.prefix)):
        override_match = re.match(scheme.override_pattern, tag)
        if re.match(scheme.check_pattern, tag):
            tags.append(tag)
        elif override_match:
            overrides[override_match.group(1)] = override_match.group(0)
        else:
            print("W: non-compliant upstream tag {}".format(tag), file=sys.stderr)
            errors.append(tag)

    for override in overrides.keys():
        if override in tags:
            idx = tags.index(override)
            tags.insert(idx, overrides[override])
            tags.pop(idx+1)

    return tags, errors


def git_check_repo(tag_schemes):
    '''
    check the repo for bad ref names
    '''
    for tag_scheme in tag_schemes:
        _, errors = git_checked_tag_list(tag_scheme)
        if len(errors):
            print("{} errors found in your tagging scheme".format(len(errors)), file=sys.stderr)
        else:
            print("OK scheme {}".format(tag_scheme.prefix))


def list_pairs(li):
    '''
    return consecutive pairs in the list e.g.
    [0, 1, 2, 3] => [(0, 1), (1, 2), (2, 3)]
    '''
    ret = []
    while len(li) > 2:
        ret.append(tuple(li[0:2]))
        li.pop(0)
    return ret


def git_pretty_commit(
        commit, 
        as_list=False, 
        stripped=False, 
        delim='\t',
        log_format=["%H", "%an", "%ae", "%s"]):
    '''
    returns pretty print log of commit
    '''
    string_out = None
    try:
        output = subprocess.check_output(
            ["git",
            "log",
            "--pretty=format:{}".format(delim.join(log_format)),
            commit,
            "^{0}~1".format(commit)],
            stderr=subprocess.STDOUT).strip()

        string_out = output.decode('utf-8', 'ignore')

    except subprocess.CalledProcessError as e:
        print("E: {}".format(e.output.decode('utf-8', 'ignore')))
        raise SystemExit(1)

    if stripped:
        string_out = string_out.strip()

    if as_list:
        return string_out.split(delim)
    else:
        return string_out



def git_deltas(git_tags, formatter):
    pairs = list_pairs(git_tags)

    for pair in pairs:
        print("{para_begin}Delta between {} ==> {}{para_end}"
            .format(pair[0], pair[1], **formatter.table))

        formatter.out("table_begin")

        for line in lines_in_command(
            "git rev-list refs/tags/{} ^refs/tags/{}".format(pair[0], pair[1])):

            formatter.out("row_begin")
            rows = git_pretty_commit(line, as_list=True, stripped=True, delim="\t")
            for row in rows:
                print("{column_begin}{:20}{column_end}".format(
                    row,
                    **formatter.table), end=' ')
            print()
            formatter.out("row_end")

        formatter.out("table_end")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse arguments')
    parser.add_argument('--format', type=str, default='text')
    parser.add_argument('action', metavar='action', type=str, nargs=1)
    args = parser.parse_args(sys.argv[1:])

    if args.action[0] == 'check':
        git_check_repo([UPSTREAM_TAG_SCHEME])
    elif args.action[0] == 'upstream-deltas':
        git_deltas(
            git_checked_tag_list(UPSTREAM_TAG_SCHEME)[0],
            formatter=Formatter(FORMATS[args.format]))
    else:
        print("unknown action {}".format(args.action), file=sys.stderr)
