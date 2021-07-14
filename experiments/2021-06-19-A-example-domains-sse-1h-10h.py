#! /usr/bin/env python

import project


DOMAINS = [
    "barman", "blocksworld", "childsnack", "driverlog", "floortile", "grid", "schedule", "tpp",
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
SMAC_RUNS_PER_DOMAIN = 10
PLANNER = project.get_singularity_planner("sse.sif")
EXTRA_OPTIONS = []

if not project.REMOTE:
    SMAC_RUNS_PER_DOMAIN = 1
    EXTRA_OPTIONS += ["--max-configurations", "1"]

domains_and_planners = [(domain, str(PLANNER)) for domain in DOMAINS]

exp = project.get_smac_experiment(domains_and_planners, SMAC_RUNS_PER_DOMAIN, ATTRIBUTES, EXTRA_OPTIONS)
exp.run_steps()
