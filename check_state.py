"""
check_state.py - check the state of a set of related projects
(last commit, last modified file), to ensure latest work is being used.

Terry Brown, TerryNBrown@gmail.com, Mon Jul 24 15:13:32 2017
"""

import argparse
import getpass
import json
import os
import shlex
import shutil
import sqlite3
import tempfile
import time

from collections import defaultdict
from subprocess import Popen, PIPE

# GLOBAL
settings_dir = None  # set by tempfile.mkdtemp() in pull_settings()

n3m_list = 'nnnmp0', 'pypanart', 'nnm2'


json_state_file = "check_state_info.json"
if not os.path.exists(json_state_file):
    json.dump({'obs':{}}, open(json_state_file, 'w'))
shelf = json.load(open(json_state_file))


def check_paths(db, set_, instance):
    """check_paths - check that the paths for an instance exist

    :param dict db: set data
    :param str set_: set
    :param str instance: instance
    :return: True if all paths found
    :rtype: bool
    """

    cur_path = None
    print("")
    print_info(headers=True)
    states = []
    for entry in db['set'][set_]['instance'][instance]['folders']:
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
                'set': set_, 'instance': instance, 'subdir': subdir,
            }
            info.update(get_file_stats(subdir))
            if os.path.exists(os.path.join(subdir, '.git')):
                info.update(get_git_info(subdir))
            print_info(info)
            states.append(info)

    return states
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
    for subpath, dirs, files in os.walk(path):
        dirs[:] = [i for i in dirs if i != '.git']  # don't consider git files for latest
        for filename in files:
            info['file_count'] += 1
            filepath = os.path.join(subpath, filename)
            stat = os.stat(filepath)
            if info['latest'] < stat.st_mtime:
                info['latest'] = stat.st_mtime
                info['latest_file'] = filepath
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

    # fix MinGW shell mangling
    opt.repo = opt.repo.replace('\\', '/').replace(':/', '://')

    return opt





def make_parser():
    """build an argparse.ArgumentParser, don't call this directly,
       call get_options() instead.
    """

    parser = argparse.ArgumentParser(
        description="Check the state of a set of related projects\n"
        "Known sets / instances:\n\n",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    repo = "git@gitlab.com:%s/check_state_info.git" % getpass.getuser()
    parser.add_argument("--repo", default=repo,
        help="Git repo. to store check_state settings / results"
    )
    parser.add_argument("--list", action='store_true',
        help="List sets / instances from repo."
    )
    parser.add_argument('set', nargs='?',
        help="Set to check"
    )
    parser.add_argument('instance', nargs='?',
        help="Instance to check"
    )

    return parser


def print_info(info=None, headers=False):
    """print_info - print table of subpath statuses

    :param dict info: info to print
    :param bool headers: don't print info, just print headers
    """

    fmt = "%10s %6s %4s %17s %8s %9s"

    YN = lambda x: 'Y' if x else 'N'

    if headers:
        print(fmt % ('subdir', 'rem_ok', 'mods', 'last', 'files', 'size'))
        return

    print(fmt % (
        os.path.basename(info['subdir']), 
        YN(not info['remote_differs']),
        YN(info['mods']), 
        time_fmt(info['latest']),
        info['file_count'],
        sizeof_fmt(info['bytes']),
        
    ))

def pull_settings(opt):
    """fetch_settings - get settings from git
    """

    global settings_dir
    settings_dir = tempfile.mkdtemp()
    print("[fetching settings from repo.]")
    cmd = shlex.split('git clone "%s" "%s"' % (opt.repo, settings_dir))
    proc = Popen(cmd, stderr=PIPE)
    _, err = proc.communicate()
    if proc.returncode:
        print("\nCloning git repo failed\n")
        print(err)
        exit(10)
    sets = json.load(open(os.path.join(settings_dir, "check_state_settings.json")))
    # expand ':foo' to sets['sub']['foo']
    for set_ in sets['set']:
        for instance in sets['set'][set_]['instance']:
            folders = sets['set'][set_]['instance'][instance]['folders']
            folders[:] = [
                sets['sub'][i[1:]] if i[0] == ':' else i for i in folders
            ]
    others = os.path.join(settings_dir, "check_state_info.json")
    if os.path.exists(others):
        others = json.load(open(others))
    else:
        others = {'obs':{}}
    return sets, others
def push_settings(others):
    """fetch_settings - get settings from git
    """

    global settings_dir
    json.dump(
        others,
        open(os.path.join(settings_dir, "check_state_info.json"), 'w'),
        indent=0
    )
    print("\n[storing results in repo.]")
    for cmd in [
        'git -C "%s" add check_state_info.json',
        'git -C "%s" commit -m "updated"',
        'git -C "%s" push',
    ]:
        cmd = shlex.split(cmd % settings_dir)
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        _, err = proc.communicate()
        if proc.returncode:
            print("\nGit command failed\n")
            print(' '.join(cmd))
            print(err)
            exit(10)
def time_fmt(t):
    """time_fmt - format time

    :param float t: time to format
    :return: formatted time
    :rtype: str
    """

    return time.strftime("%a %b %d, %H:%M", time.localtime(t))

def sizeof_fmt(num, suffix='B'):
    # https://stackoverflow.com/a/1094933/1072212
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def main():
    global settings_dir

    opt = get_options()

    sets, others = pull_settings(opt)

    if opt.list:
        print("\nKnown sets / instances\n")
        info = []
        for set_ in sets['set']:
            info.append("%s" % set_)
            for instance in sets['set'][set_]['instance']:
                info.append("    %s" % instance)
        print('\n'.join(info)+'\n')
        return

    info = check_paths(sets, opt.set, opt.instance)
    others['obs'].setdefault(opt.set, {})[opt.instance] = {
        'updated': time.time(),
        'subdirs': info,
    }
    for instance in others['obs'][opt.set]:
        if instance == opt.instance:
            continue
        obs = others['obs'][opt.set][instance]
        print("%s %s" % (instance, time_fmt(obs['updated'])))
        for subdir in obs['subdirs']:
            print_info(subdir)

    push_settings(others)
    shutil.rmtree(settings_dir, ignore_errors=True)
    exit()
if __name__ == '__main__':
    try:
        main()
    finally:
        json.dump(shelf, open(json_state_file, 'w'), indent=4)

