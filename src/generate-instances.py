#! /usr/bin/env python3

import argparse
import json
import logging
from pathlib import Path
import random
import re
import resource
import subprocess
import sys
import warnings

import domains
from runner import Runner
import utils


warnings.simplefilter(action="ignore", category=FutureWarning)
warnings.simplefilter(action="ignore", category=DeprecationWarning)


import numpy as np

from smac.configspace import ConfigurationSpace
from smac.scenario.scenario import Scenario
from smac.facade.smac_hpo_facade import SMAC4HPO
from smac.initial_design.default_configuration_design import DefaultConfiguration


DIR = Path(__file__).resolve().parent
REPO = DIR.parent


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", help="Domain name")
    parser.add_argument(
        "planner",
        help="Path to Singularity-based planner. "
        "It must accept three parameters: domain_file problem_file plan_file",
    )

    parser.add_argument(
        "--max-configurations",
        type=int,
        default=sys.maxsize,
        help="Maximum number of configurations to try (default: %(default)s)",
    )

    parser.add_argument(
        "--overall-time-limit",
        type=float,
        default=20 * 60 * 60,
        help="Maximum total time for generating instances (default: %(default)ss)",
    )

    parser.add_argument(
        "--planner-time-limit",
        type=float,
        default=1800,
        help="Maximum time in seconds for each configuration (default: %(default)ss)",
    )

    parser.add_argument(
        "--planner-memory-limit",
        type=float,
        default=4 * 1024,  # 4 GiB
        help="Maximum memory for each configuration in MiB (default: %(default)ss)",
    )

    parser.add_argument("--debug", action="store_true", help="Print debug info")

    parser.add_argument(
        "--random-seed",
        type=int,
        default=0,
        help="Initial random seed for SMAC and our internal random seeds (default: %(default)d)",
    )

    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Run each parameter configuration only once (with seed 0).",
    )

    parser.add_argument(
        "--generators-dir",
        default=REPO / "pddl-generators",
        help="Path to directory containing the PDDL generators (default: %(default)s)",
    )

    parser.add_argument(
        "--smac-output-dir",
        default="smac",
        help="Directory where to store logs and temporary files (default: %(default)s)",
    )

    return parser.parse_args()


ARGS = parse_args()
GENERATORS_DIR = Path(ARGS.generators_dir)
SMAC_OUTPUT_DIR = Path(ARGS.smac_output_dir)
SMAC_RUN_DIR = None  # Set after SMAC object is created.
random.seed(ARGS.random_seed)

utils.setup_logging(ARGS.debug)

DOMAINS = domains.get_domains()
logging.debug(f"{len(DOMAINS)} domains available: {sorted(DOMAINS)}")
DOMAIN = DOMAINS[ARGS.domain]

for domain in DOMAINS:
    if (
        not (GENERATORS_DIR / domain / "domain.pddl").is_file()
        and not DOMAINS[domain].uses_per_instance_domain_file()
    ):
        sys.exit(f"Error: domain.pddl missing for {domain}")

PLANNER = Path(ARGS.planner)
if not PLANNER.is_file():
    sys.exit(f"planner not found: {PLANNER}")
RUNNER = Runner(
    DOMAIN,
    ["bash", DIR / "run-singularity.sh", PLANNER, "domain.pddl", "problem.pddl", "sas_plan"],
    ARGS.planner_time_limit,
    ARGS.planner_memory_limit,
    GENERATORS_DIR,
)


def show_error_log(plan_dir):
    try:
        with open(plan_dir / "run.err") as f:
            output = f.read()
    except FileNotFoundError:
        pass
    else:
        logging.error(f"\n\nError log:\n\n{output}\n\n")


def parse_runtime(plan_dir):
    with open(plan_dir / "run.log") as f:
        output = f.read()
    logging.debug(f"\n\nPlanner output:\n\n{output}\n\n")
    match = re.search("Singularity runtime: (.+?)s", output)
    runtime = float(match.group(1))
    runtime = max(0.1, runtime)  # log(0) is undefined.
    return runtime


def store_results(cfg, seed, plan_dir, exitcode):
    # Save results in JSON file.
    results = {
        "domain": ARGS.domain,
        "parameters": cfg,
        "seed": int(seed),
        "planner_exitcode": exitcode,
    }
    if exitcode == 0:
        results["runtime"] = parse_runtime(plan_dir)
    with open(plan_dir / "properties.json", "w") as props:
        json.dump(
            results,
            props,
            indent=2,
            separators=(",", ": "),
            sort_keys=True,
        )


def evaluate_configuration(cfg, seed=1):
    peak_memory = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    cfg = cfg.get_dictionary()

    try:
        cfg = DOMAIN.adapt_parameters(cfg)
    except domains.IllegalConfiguration as err:
        logging.info(f"Skipping illegal configuration {cfg}: {err}")
        return 100

    logging.info(f"[{peak_memory} KB] Evaluate configuration {cfg} with seed {seed}")

    try:
        plan_dir = RUNNER.generate_input_files(cfg, seed, SMAC_RUN_DIR)
    except subprocess.CalledProcessError as err:
        logging.error(f"Failed to generate task {cfg}: {err}")
        return 100

    exitcode = RUNNER.run_planner(plan_dir)
    store_results(cfg, seed, plan_dir, exitcode)
    show_error_log(plan_dir)
    if exitcode == 0:
        logging.info(f"Solved task {cfg}")
    else:
        logging.info(f"Failed to solve task {cfg}")
        return 100

    return 0


# Build Configuration Space which defines all parameters and their ranges.
cs = ConfigurationSpace()

cs.add_hyperparameters(DOMAIN.attributes)

scenario = Scenario(
    {
        "run_obj": "quality",
        # max. number of function evaluations
        "ta_run_limit": ARGS.max_configurations,
        # maximum total runtime for function evaluations
        "algo_runs_timelimit": ARGS.overall_time_limit,
        "wallclock_limit": ARGS.overall_time_limit,
        "cs": cs,
        "deterministic": ARGS.deterministic,
        # memory limit for evaluate_cfg (we set the limit ourselves)
        "memory_limit": None,
        # time limit for evaluate_cfg (we cut off planner runs ourselves)
        "cutoff": None,
        "output_dir": f"{SMAC_OUTPUT_DIR}",
        # Disable pynisher.
        "limit_resources": False,
        # Run SMAC in parallel.
        "shared_model": True,
        "input_psmac_dirs": f"{SMAC_OUTPUT_DIR}/run_*",
    }
)

# When using SMAC4HPO, the default configuration has to be requested explicitly
# as first design (see https://github.com/automl/SMAC3/issues/533).
smac = SMAC4HPO(
    scenario=scenario,
    initial_design=DefaultConfiguration,
    rng=np.random.RandomState(ARGS.random_seed),
    tae_runner=evaluate_configuration,
)
SMAC_RUN_DIR = smac.output_dir
logging.info(f"SMAC run dir: {SMAC_RUN_DIR}")

default_cfg = cs.get_default_configuration()
logging.info(f"Default config: {default_cfg}")

logging.info("Optimizing...")
incumbent = smac.optimize()
