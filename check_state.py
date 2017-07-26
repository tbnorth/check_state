"""
check_state.py - check the state of a set of related projects
(last commit, last modified file), to ensure latest work is being used.

Terry Brown, TerryNBrown@gmail.com, Mon Jul 24 15:13:32 2017
"""

import argparse
import os
import shlex
import sqlite3
import time

from collections import defaultdict
from subprocess import Popen, PIPE

n3m_list = 'nnm2', 'nnnmp0', 'pypanart'

SETS = {
    'set': {
        'nearshore': {
            'instances': {
                'otter': {
                    'folders': [
                        "/mnt/edata/edata/+",
                        n3m_list,
                        'tnbbib',
                    ],
                },
                'epadt': {
                    'folders': [
                        r"d:\repo\+",
                        n3m_list,
                        'tnbbib',
                    ],
                },
            },
        },
    },
}


def check_paths(db, set, instance):
    """check_paths - check that the paths for an instance exist

    :param dict db: set data
    :param str set: set
    :param str instance: instance
    :return: True if all paths found
    :rtype: bool
    """

    cur_path = None
    print_info(headers=True)
    for entry in db['set'][set]['instances'][instance]['folders']:
        not_list = not isinstance(entry, (tuple, list))
        if not_list and os.path.basename(entry) == '+':
            # a new base path for relative paths
            cur_path = os.path.dirname(entry)
            continue
        subdirs = [entry] if not_list else entry
        for subdir in subdirs:
            if not os.path.isabs(subdir):
                subdir = os.path.join(cur_path, subdir)
            if not os.path.exists(subdir):
                print("No path '%s'" % subdir)
                continue
            if not os.path.isdir(subdir):
                raise Exception("Path '%s' is not a directory" % subdir)
            info = {
                'set': set, 'instance': instance, 'subdir': subdir,
                'date': time.asctime(),
            }
            info.update(get_file_stats(subdir))
            if os.path.exists(os.path.join(subdir, '.git')):
                info.update(get_git_info(subdir))
            print_info(info)
def get_concur(filepath=None):
    """
    get_concur - get DB connection and cursor - may create ~/.check_state

    :param str filepath: optional path to data file
    :return: connection and cursor
    :rtype: tuple
    """

    filepath = filepath or get_datafile()
    filedir = os.path.dirname(filepath)
    if not os.path.exists(filedir):
        os.mkdir(filedir)
    con = sqlite3.connect(filepath)
    return con, con.cursor()
def get_datafile():
    """get_datafile - get name of DB
    """

    return os.path.join(os.path.expanduser('~'), '.check_state', 'check_state.db')
def get_file_stats(path):
    """get_file_stats - get most recent modification time etc. for a directory tree

    :param str path: top of directory tree
    :return: {'latest': timestamp}
    :rtype: dict
    """

    info = defaultdict(lambda: 0)
    for subpath, dirs_, files in os.walk(path):
        for filename in files:
            info['file_count'] += 1
            filepath = os.path.join(subpath, filename)
            stat = os.stat(filepath)
            info['latest'] = max(info['latest'], stat.st_mtime)
            info['bytes'] += stat.st_size
    return info
def get_git_info(path):
    """get_git_info - git status in directory

    :param str path: path to git repo
    :return: dict of info.
    """

    info = {
        'commit': 'rev-parse HEAD',
        'branch': 'rev-parse --abbrev-ref HEAD',
        'mods': 'diff-index HEAD --',
        'remotes': 'ls-remote',
    }

    for key in info:
        proc = Popen(shlex.split('git -C "%s" %s' % (path, info[key])), 
            stdout=PIPE, stderr=PIPE)
        info[key], _ = proc.communicate()
        info[key] = info[key].strip()

    info['mods'] = info['mods'] or None

    info['remote_differs'] = False
    if info['remotes']:
        ours = [
            i for i in info['remotes'].split('\n')
            if i.endswith('refs/heads/'+info['branch'])
        ]
        for commit in ours:
            info['remote_differs'] = info['remote_differs'] or \
                commit.split()[0] != info['commit']
    del info['remotes']

    return info
def get_options(args=None):
    """
    get_options - use argparse to parse args, and return a
    argparse.Namespace, possibly with some changes / expansions /
    validatations.

    Client code should call this method with args as per sys.argv[1:],
    rather than calling make_parser() directly.

    :param [str] args: arguments to parse
    :return: options with modifications / validations
    :rtype: argparse.Namespace
    """
    opt = make_parser().parse_args(args)

    # modifications / validations go here

    return opt





def make_parser():
    """build an argparse.ArgumentParser, don't call this directly,
       call get_options() instead.
    """
    parser = argparse.ArgumentParser(
        description="""Check the state of a set of related projects""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # parser.add_argument("--<|foo|>", action='store_true',
    #     help="<|help|>"
    # )
    # parser.add_argument('<|positional(s)|>', type=str, nargs='+',
    #     help="<|help|>"
    # )

#   #   requiredNamed = parser.add_argument_group('required named arguments')

#   #   requiredNamed.add_argument("--config",
    #     help="Path to config. file, e.g. 'something.conf.py'",
    #     metavar='FILE'
    # )

    return parser


def print_info(info=None, headers=False):
    """print_info - print table of subpath statuses

    :param dict info: info to print
    :param bool headers: don't print info, just print headers
    """

    fmt = "% 10s % 6s % 4s % 20s"
    YN = lambda x: 'Y' if x else 'N'

    if headers:
        print(fmt % ('subdir', 'rem_ok', 'mods', 'last'))
        return

    print(fmt % (
        os.path.basename(info['subdir']), YN(not info['remote_differs']),
        YN(info['mods']), info['latest'],
    ))

def main():
    opt = get_options()

    # con, cur = get_concur()

    check_paths(SETS, 'nearshore', 'epadt')
if __name__ == '__main__':
    main()
