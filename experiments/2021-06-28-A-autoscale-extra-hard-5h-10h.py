#! /usr/bin/env python

import project


ATTRIBUTES = [
    project.Attribute("final_value", min_wins=True),
    project.Attribute("evaluated_configurations", min_wins=False),
    project.Attribute("wallclock_time", min_wins=None),
    project.Attribute("incumbent_changed", min_wins=False),
    project.Attribute("evaluation_time", min_wins=False),
    "error", "run_dir", "final_*", "smac_exit_code",
    "max_shared_runs",
]
SMAC_RUNS_PER_DOMAIN = 50
EXTRA_OPTIONS = []

DOMAINS_AND_PLANNERS = [
    ("agricola", "fd1906-lama-first.img"),
    ("mystery", "ipc2018-agl-lapkt-dual-bfws.img"),
    ("pathways", "ipc2014-agl-mpc.img"),
    ("tetris", "ipc2018-agl-lapkt-bfws-pref.img")
]

if not project.REMOTE:
    SMAC_RUNS_PER_DOMAIN = 1
    EXTRA_OPTIONS += ["--max-configurations", "3"]

exp = project.get_smac_experiment(DOMAINS_AND_PLANNERS, SMAC_RUNS_PER_DOMAIN, ATTRIBUTES, EXTRA_OPTIONS)
exp.run_steps()
