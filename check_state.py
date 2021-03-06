"""
check_state.py - check the state of a set of related projects
(last commit, last modified file), to ensure latest work is being used.

Terry Brown, TerryNBrown@gmail.com, Mon Jul 24 15:13:32 2017
"""

from __future__ import print_function

import argparse
import getpass
import json
import os
import re
import shlex
import shutil
import sqlite3
import sys
import tempfile
import time

from collections import defaultdict, OrderedDict
from copy import deepcopy
from subprocess import Popen, PIPE

# GLOBAL
settings_dir = None  # set by tempfile.mkdtemp() in pull_settings()

n3m_list = 'nnnmp0', 'pypanart', 'nnm2'
def basename(path):
    """basename - basename of path, where paths are from different
    OSs, so os.path.basename doesn't work.

    :param str path: path to basename
    :return: basename
    :rtype: str
    """

    return path.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]

def dirname(path):
    """dirname - dirname of path, where paths are from different
    OSs, so os.path.dirname doesn't work.

    :param str path: path to dirname
    :return: dirname
    :rtype: str
    """

    return path.replace('\\', '/').rstrip('/').rsplit('/', 1)[-2]

def isabs(path):
    """isabs - OS neutral os.path.isabs

    :param str path: path to check
    :return: True if path is absolute
    :rtype: bool
    """

    return path.startswith('/') or len(path) > 1 and path[1] == ':'
def check_paths(db, set_, instance):
    """check_paths - check that the paths for an instance exist

    :param dict db: set data
    :param str set_: set
    :param str instance: instance
    :return: True if all paths found
    :rtype: bool
    """

    print("")
    states = []

    print("%s/%s: " % (set_, instance), end='')
    for subdir in expand_folders(db, set_, instance):
        if not os.path.exists(subdir):
            print("\nNo path '%s'" % subdir)
            continue
        if not os.path.isdir(subdir):
            raise Exception("\nPath '%s' is not a directory" % subdir)
        info = {
            'set': set_, 'instance': instance, 'subdir': subdir,
        }
        info.update(get_file_stats(subdir))
        if os.path.exists(os.path.join(subdir, '.git')):
            info.update(get_git_info(subdir))
        print(os.path.basename(subdir), end=', ')
        sys.stdout.flush()
        states.append(info)
    print("\n")

    return states

def do_list(opt, sets, others):
    """Just list known sets / instances"""
    print("\nKnown sets / instances\n")
    info = []
    for set_ in sets['set']:
        if set_ == "_TEMPLATE_":
            continue
        info.append("%s" % set_)
        for instance in sets['set'][set_]['instance']:
            info.append("    %s" % instance)
    print('\n'.join(info)+'\n')
    return

def do_check_all(opt, sets, others, config):
    """Check all projects"""

    for set_ in sets['set']:
        if set_ == '_TEMPLATE_':
            continue
        opt.set = set_
        set_set_instance(opt, config, sets)
        opt.instance = opt.instance or opt.all
        do_check_one(opt, sets, others, config)
def do_check_one(opt, sets, others, config):

    info = check_paths(sets, opt.set, opt.instance)
    others['obs'].setdefault(opt.set, {})[opt.instance] = {
        'updated': time.time(),
        'subdirs': info,
    }

    show_results(sets, others, opt.set, opt.instance)
    seen = config.setdefault('seen', [])
    if [opt.set, opt.instance] not in seen:
        seen.append([opt.set, opt.instance])

def do_show_stored(opt, sets, others):
    """Just list results"""

    for set_ in sets['set']:
        if opt.set and not opt.guessed_instance and set_ != opt.set \
           or set_ == '_TEMPLATE_':
            continue
        print("\nStored results: %s\n" % set_)
        show_results(sets, others, set_, opt.instance)

    return

def expand_folders(db, set_, instance):

    if instance not in db['set'][set_]['instance']:
        return []

    folders = []
    cur_path = None

    for entry in db['set'][set_]['instance'][instance]['folders']:
        not_list = not isinstance(entry, (tuple, list))
        if not_list and basename(entry) == '+':
            # a new base path for relative paths
            cur_path = entry.rstrip('+/\\')
            continue
        subdirs = [entry] if not_list else entry
        for subdir in subdirs:
            if not isabs(subdir):
                if not cur_path:
                    raise Exception(
                        "Relative path '%s' before any base path in '%s/%s'" % (
                        subdir, set_, instance))
                subdir = os.path.join(cur_path, subdir)
            folders.append(subdir)

    return folders

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

    # {foo} replaced with info['foo'], so order matters
    info = OrderedDict([
        ('commit', 'rev-parse HEAD'),  # commit hash
        ('branch', 'rev-parse --abbrev-ref HEAD'),  # branch name
        # unix time of commit
        ('commit_time', "rev-list --format=format:'%ct' --max-count=1 {commit}"),
        ('mods', 'diff-index HEAD --'),  # detect uncommitted changes
        ('remotes', 'ls-remote'),  # list of remote commit hashes
    ])

    for key in info:
        cmd = info[key]
        for subst in re.finditer(r"\{[a-z]+}", cmd):
            subst = subst.group()
            cmd = cmd.replace(subst, info[subst.strip('{}')])
        proc = Popen(shlex.split('git -C "%s" %s' % (path, cmd)),
            stdout=PIPE, stderr=PIPE)
        info[key], _ = proc.communicate()
        info[key] = info[key].strip()

    info['mods'] = info['mods'] or None

    info['commit_time'] = float(info['commit_time'].split('\n')[1])

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

def get_local_config():
    """get_local_config - read local config. file, return dict.

    Not to be confused with the "main" config. (sets) returned by pull_settings,
    and stored in a (probably) remote git repo.
    """
    path = os.path.expanduser(os.path.join("~", ".check_state"))
    if not os.path.exists(path):
        os.mkdir(path)
    path = os.path.join(path, "check_state.conf.json")
    if os.path.exists(path):
        with open(path) as config:
            config = json.load(config)
    else:
        config = {}
    return config

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

    # fix MinGW shell mangling  FIXME: breaks Windows paths to local repos
    opt.repo = opt.repo.replace('\\', '/')
    if '://' not in opt.repo:  # comes through correctly from JSON
        opt.repo = opt.repo.replace(':/', '://')

    return opt

def set_set_instance(opt, config, sets):
    """set_set_instance - guess and update set and instance if not set in opt,
    also update config.  Sets bool opt.guessed_instance.

    `set` and `instance` are positional parameters, so you can set instance
    without setting set.

    :param argparse.Namespace opt: options from command line
    :param dict config: from get_local_config()
    :param dict sets: main check_state config. stored in repo.
    :returns: True is succeeds / unneeded, otherwise False
    """

    cwd = os.getcwd()
    choices = []
    seen = config.setdefault('seen', [])
    opt.guessed_instance = False

    if opt.set and opt.set not in sets['set']:
        raise Exception("Project '%s' not known.\n%s" % (
            opt.set, ' '.join([i for i in sets['set'] if i != '_TEMPLATE_'])))

    if not opt.instance:  # try to guess based on path or project
        if opt.set:
            for instance in sets['set'][opt.set]:
                if [opt.set, instance] in seen:
                    opt.instance = instance
                    opt.guessed_instance = True
                    return True
        for set_ in sets['set']:
            if set_ == '_TEMPLATE_' or opt.set and set_ != opt.set:
                continue
            for instance in sets['set'][set_]['instance']:
                folders = expand_folders(sets, set_, instance)
                folders = [os.path.realpath(i) for i in folders]
                choice = [set_, instance]  # must use list, stored in JSON
                levels = cwd.split(os.path.sep)
                if levels[0] and levels[0][-1] == ':':
                    levels[0] += '\\'  # Windows
                elif levels[0] == '':
                    levels[0] = '/'  # unix
                while levels:  # check parents
                    if os.path.join(*levels) in folders:
                        if choice in seen:
                            opt.set, opt.instance = choice
                            opt.guessed_instance = True
                            return True
                        choices.append(choice)
                    del levels[-1]
        if len(choices) > 1:
            print("\nPath exists in multiple instances")
            print("Please run one of the following to set for this machine\n")
            for set_, instance in choices:
                print("python %s --repo %s %s %s" % (sys.argv[0], opt.repo, set_, instance))
            print("")
            return False
        if len(choices) == 1:
            opt.set, opt.instance = choices[0]
            print("\nGuessing project / instance '%s' / '%s' from folder" % (
                opt.set, opt.instance))
            assert choices[0] not in seen
            seen.append(choices[0])
            opt.guessed_instance = True
            return True
        else:
            print("\nCan't guess project / instance from current folder")
            print("%s / %s" % (opt.set, opt.instance))
            return False

    return True

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
    repo = get_local_config().get('repo') or repo
    parser.add_argument("--repo", default=repo,
        help="Git repo. to store check_state settings / results"
    )
    parser.add_argument("--no-store", action='store_true',
        help="Don't update the repo. results on exit"
    )
    parser.add_argument("--list", action='store_true',
        help="List sets / instances from repo."
    )
    parser.add_argument("--show-stored", action='store_true',
        help="Don't re-analyze, just show stored results. "
             "Without `set`, show all sets."
    )
    parser.add_argument("--all", metavar='INSTANCE',
        help="Check all folders under all projects, use INSTANCE where unclear"
    )
    parser.add_argument('set', nargs='?',
        help="Set to check"
    )
    parser.add_argument('instance', nargs='?',
        help="Instance to check"
    )

    return parser

def print_info(info=None, headers=False, latest=None, mark_commit=False,
               mark_date=False):
    """print_info - print table of subpath statuses

    :param dict info: info to print
    :param bool headers: don't print info, just print headers
    :param date latest: (NOT USED) latest date for file mod.
    :param bool mark_commit: * commit to indicate mismatch
    :param bool mark_date: * commit date to indicate latest
    """

    fmt = "%15s %6s %4s %8s %9s %8s %13s"

    YN = lambda x: 'Y' if x else 'N'

    if headers:
        print(fmt % ('subdir', 'rem_ok', 'mods', 'files', 'size', 'commit', 'commit_time'))
        print(fmt % ('', '', '', '', '', '*=mixed', '*=latest'))
        return

    # highligh latest modification time
    this_latest = time_fmt(info['latest'])
    this_latest += '*' if info['latest'] == latest else ' '

    commit_time = info.get('commit_time', '')
    if commit_time:
        commit_time = time_fmt(commit_time)

    print(fmt % (
        # can't use os.path.basename() as data mixes paths from different OSs
        basename(info['subdir']),
        YN(not info['remote_differs']),
        YN(info['mods']),
        # this_latest,
        info['file_count'],
        sizeof_fmt(info['bytes']),
        info.get('commit', '')[:7] + ('*' if mark_commit else ' '),
        commit_time + ('*' if mark_date else ' '),
    ))

def pull_settings(opt):
    """fetch_settings - get settings from git
    """

    global settings_dir
    settings_dir = tempfile.mkdtemp()
    print("[get settings from: %s]" % opt.repo)
    cmd = shlex.split('git clone --depth=1 "%s" "%s"' % (opt.repo, settings_dir))
    proc = Popen(cmd, stderr=PIPE)
    _, err = proc.communicate()
    if proc.returncode:
        print("\nCloning git repo failed\n")
        print(err)
        exit(10)
    sets = json.load(open(os.path.join(settings_dir, "check_state_settings.json")))
    # expand ':foo' to sets['sub']['foo']
    for set_ in sets['set']:
        if set_ == "_TEMPLATE_":
                continue
        for instance in sets['set'][set_]['instance']:
            folders = sets['set'][set_]['instance'][instance]['folders']
            if folders[0] == ':':
                # same as another instance
                sets['set'][set_]['instance'][instance]['folders'] = \
                    sets['set'][set_]['instance'][folders[1:]]['folders']
                continue
            folders[:] = [  # replace lists
                sets['sub'][i[1:]] if i[0] == ':' else i for i in folders
            ]
    others = os.path.join(settings_dir, "check_state_info.json")
    if os.path.exists(others):
        others = json.load(open(others))
    else:
        others = {'obs': {}}
    return sets, others

def push_settings(others):
    """fetch_settings - get settings from git
    """

    global settings_dir
    json.dump(
        others,
        open(os.path.join(settings_dir, "check_state_info.json"), 'w'),
        indent=0,
        sort_keys=True  # minimizes git diffs
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

    return time.strftime("%m/%d-%H:%M", time.localtime(t))

def show_results(sets, others, set_, cur_instance):

    print_info(headers=True)
    # sort this instance to the bottom of the list
    keys = sorted(others['obs'][set_], key=lambda x: x == cur_instance)

    # find latest file change for each subdir ACROSS INSTANCES
    # also check commits match
    latest_mod = defaultdict(lambda: set())  # latest file modification, not that useful
    commit_date = defaultdict(lambda: set())  # latest (newest) commit date
    commit = defaultdict(lambda: set())  # commit hashes for subdirs
    for instance in keys:
        obs = others['obs'][set_][instance]
        for subdir in obs['subdirs']:
            dir_ = basename(subdir['subdir'])
            commit[dir_].add(subdir['commit'])
            commit_date[dir_].add(subdir.get('commit_time'))
            latest_mod[dir_].add(subdir['latest'])
    max_commit_date = {k:max(commit_date[k]) for k in commit_date}
    max_mod_date = {k:max(latest_mod[k]) for k in latest_mod}

    mixed_commits = set()  # to see if there are any in commit from above
    for instance in keys:
        obs = others['obs'][set_][instance]
        print("%s %s" % (instance, time_fmt(obs['updated'])))
        for subdir in obs['subdirs']:
            dir_ = basename(subdir['subdir'])
            if len(commit[dir_]) != 1:
                mark_commit = True
                mixed_commits.add(dir_)
            else:
                mark_commit = False
            print_info(
                subdir,
                latest=max_mod_date.get(dir_),
                mark_commit=mark_commit,
                mark_date=(subdir.get('commit_time') == max_commit_date[dir_])
            )

    if mixed_commits:
        print("\nWARNING: mixed commits for: %s" % (', '.join(mixed_commits)))

    if cur_instance:
        msg = "\nPossible remedies\n"
        for subdir in others['obs'][set_][cur_instance]['subdirs']:
            if subdir['mods']:
                print("%scd '%s' && git diff && git commit -a && git push" %
                    (msg, subdir['subdir']))
                msg = ""
            if subdir['remote_differs']:
                print("%scd '%s' && git pull  # or maybe push" % 
(msg, subdir['subdir']))
                msg = ""
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

    config = get_local_config()
    orig_config = deepcopy(config)
    config['repo'] = opt.repo  # which possibly came from config, see make_parser()

    set_set_instance(opt, config, sets)  # guess opt.set and opt.instance if not set

    if opt.list:
        do_list(opt, sets, others)
        return

    if not opt.instance and not opt.all:
        exit()

    if opt.show_stored:
        do_show_stored(opt, sets, others)
        return

    if opt.all:
        do_check_all(opt, sets, others, config)
        if opt.no_store:
            print("\n[NOT storing results to repo.]")
        else:
            push_settings(others)
        return

    do_check_one(opt, sets, others, config)

    if opt.no_store:
        print("\n[NOT storing results to repo.]")
    else:
        push_settings(others)

    shutil.rmtree(settings_dir, ignore_errors=True)

    if config != orig_config:
        print("Updating local config.")
        json.dump(
            config,
            open(os.path.expanduser(os.path.join(
                "~", ".check_state", "check_state.conf.json")), 'w'),
            indent=4
        )

if __name__ == '__main__':
    main()

