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
                        "/mnt/data/data/+",
                        ":project1"
                    ]
                }
            }
        },
        "project2": {
            "instance": {
                "home": {
                    "folders": [
                        "/mnt/data/data/+",
                        ":multiscale"
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

## To do

 - [ ] time based local caching (e.g. 10 minutes) to save re-fetching settings
 - [ ] optionally don't save results to repo. when problems seen