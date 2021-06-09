#! /usr/bin/env python

import project


DOMAINS = [
    "agricola",
]
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
PLANNER = project.get_singularity_planner("fd1906-lama-first.img")
EXTRA_OPTIONS = [PLANNER]

if not project.REMOTE:
    SMAC_RUNS_PER_DOMAIN = 2
    EXTRA_OPTIONS += ["--debug", "--max-configurations", "3"]

exp = project.get_smac_experiment(DOMAINS, SMAC_RUNS_PER_DOMAIN, ATTRIBUTES, EXTRA_OPTIONS)
exp.run_steps()
