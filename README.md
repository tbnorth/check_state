# check_state.py

For projects being developed on multiple systems (work, home, laptop) and
using multiple git repositories.  Checks for uncommited changes, sync. with
upstream, latest file modification, etc.

Uses a git repo. for centralized storage of settings and results, for cross
system comparisons.

```
usage: check_state.py [-h] [--repo REPO] [--no-store] [--list]
                      [set] [instance]

Check the state of a set of related projects Known sets / instances:

positional arguments:
  set          Set to check (default: None)
  instance     Instance to check (default: None)

optional arguments:
  -h, --help   show this help message and exit
  --repo REPO  Git repo. to store check_state settings / results (default:
               git@gitlab.com:USERNAME/check_state_info.git)
  --no-store   Don't update the repo. results on exit (default: False)
  --list       List sets / instances from repo. (default: False)
```

## Example output

```
python check_state.py --repo git@gitlab.com:example/check_state_info.git nearshore otter
[fetching settings from repo.]

nnnmp0, pypanart, nnm2, tnbbib, 

         subdir rem_ok mods               last    files      size   commit
edata Mon Jul 31, 10:42
         tnbbib      Y    N Tue Jul 25, 16:33         6  815.4KiB 677b745*
         nnnmp0      Y    N Tue Jul 25, 16:26        75   22.3MiB 170bea2 
       pypanart      Y    N Tue Jul 25, 12:36*       38    3.7MiB 14c5446 
           nnm2      Y    N Tue Jul 18, 10:59       138   12.9MiB 9a33683 
epadt Mon Jul 31, 10:53
         tnbbib      Y    N Fri Jul 28, 10:54*       47   97.3MiB 677b745*
         nnnmp0      Y    N Wed Jul 26, 11:59        98   61.6MiB 170bea2 
       pypanart      Y    N Mon Jul 24, 16:23        35    2.9MiB 14c5446 
           nnm2      Y    N Thu Jul 20, 12:54     25131   77.5GiB 9a33683 
otter Wed Aug 02, 14:09
         nnnmp0      Y    N Fri Jul 28, 09:54*       66   17.4MiB 170bea2 
       pypanart      Y    N Fri Jul 21, 11:06        36    3.0MiB 14c5446 
           nnm2      Y    N Fri Jul 28, 09:54*       60    3.3MiB 9a33683 
         tnbbib      N    N Fri Jul 28, 09:58         9    4.4MiB ec7fd72*

WARNING: mixed commits for: tnbbib

Possible remedies
git -C '/mnt/edata/edata/tnbbib' pull

[storing results in repo.]

```

The instance listed last, `otter`, is always the local instance (the one
updated by this run of `check_state`.  The `tnbbib` component on otter is
has a different `HEAD` than its remote, and a different commit than the
other instances.  Remember the data for the other instances is dated, so
they may be showing `Y` for `rem_ok` (remote OK), but still be out of date.
In that case only the “mixed commits” warning would be given.

## Configuration

The config. file should be called `check_state_settings.json` and stored in
the repo. specified with `--repo`.  Here's an example:

```
{
    "sub": {
        "project1": [
            "folder1",
            "folder2",
            "folder3"
        ],
        "project2": [
            "other_folder1",
            "other_folder2"
        ]
    },
    "set": {
        "_TEMPLATE_": {
            "instance": {
                "INSTANCE0": {
                    "folders": [
                        "BASEPATH+",
                        ":SUBST_LIST"
                    ]
                }
            }
        },
        "project1": {
            "instance": {
                "work": {
                    "folders": [
                        "d:\\somepath\\+",
                        ":project1",
                        "extra_folder",
                        "C:\\absolute\\extrafolder"
                    ]
                },
                "home": {
                    "folders": [
                        "/mnt/data/+",
                        ":project1"
                    ]
                }
            }
        },
        "project2": {
            "instance": {
                "home": {
                    "folders": [
                        "/mnt/moredata/+",
                        ":project2"
                    ]
                },
                "laptop": {
                    "folders": ":home"
                }
            }
        }
    }
}
```

`sub` is a dictionary of lists that can be used when a project uses
multiple subfolders in a common root folder (examples follow).

`set` is a dictionary of projects.  `_TEMPLATE_` is a special entry that
can be copy / pasted for new projects.  `check_state.py` ignores it when
listsing projects.  Other entries in `set` are the names of projects known
to `check_state`.  The names used in `subs` don't have to match the project
names, but it's convenient if they do.  Each project has an `instance`
dictionary of known instances (home, work, etc.) of the project.  Each
instance is in turn a dictionary with a `folders` entry which lists the
paths (folders) used by the instance of the project.

Absolute paths ending in `+` are used a base path for subsequent
relative paths.  `folders` entries starting with `:` are replaced with the
list from `subs`.  So for `project1` the list of folders expands to either

```
d:\somepath\folder1 d:\somepath\folder2 d:\somepath\folder3 d:\somepath\folder4
d:\somepath\extra_folder c:\absolute\extrafolder
```

or

```
/mnt/data/folder1 /mnt/data/folder2 /mnt/data/folder3 /mnt/data/folder4
```

for the `work` and `home` instances respectively.

If two instances of a project have exactly the same layout (same common
base folder etc.), e.g. `project2`, the `folders` element for one instance
can just reference a different instance.  In this case `folders` is a string
starting with `:` rather than a list.

## To do

 - [ ] local config. to store the `--repo` setting
 - [ ] time based local caching (e.g. 10 minutes) to save re-fetching settings
 - [ ] optionally don't save results to repo. when problems seen