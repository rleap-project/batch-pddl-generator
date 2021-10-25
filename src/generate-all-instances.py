#! /usr/bin/env python3

import argparse
import logging
from pathlib import Path
import shutil
import subprocess
import os

import ConfigSpace
from ConfigSpace.util import generate_grid

import domains
import utils


DIR = Path(__file__).resolve().parent
REPO = DIR.parent
DOMAINS = domains.get_domains()
TMPDIR_NAME = "tmp"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", choices=DOMAINS, help="Domain name")
    parser.add_argument("destdir", help="Destination directory for benchmarks")
    parser.add_argument("--debug", action="store_true", help="Print debug info")
    parser.add_argument("--dry-run", action="store_true", help="Show only size of configuration space")
    parser.add_argument("--generator-time-limit", default=None, type=int, help="Time limit for generator calls")

    parser.add_argument(
        "--num-random-seeds",
        type=int,
        default=1,
        help="Number of random seeds used for each parameter configuration (default: %(default)d)",
    )

    parser.add_argument(
        "--generators-dir",
        default=REPO / "pddl-generators",
        help="Path to directory containing the PDDL generators (default: %(default)s)",
    )

    return parser.parse_args()


def generate_task(generators_dir, domain, cfg, seed, tmp_dir, output_dir, time_limit=None):
    try:
        cfg = domain.adapt_parameters(cfg)
    except domains.IllegalConfiguration as err:
        logging.warning(f"Skipping illegal configuration {cfg}: {err}")
        return

    logging.info(f"Create instance for configuration {cfg} with seed {seed}")
    try:
        plan_dir = utils.generate_input_files(generators_dir, domain, cfg, seed, tmp_dir, timeout=time_limit)
    except subprocess.CalledProcessError as err:
        logging.error(f"Failed to generate task: {err}")
        return
    except subprocess.TimeoutExpired as err:
        logging.error(f"Failed to generate task: {err}")
        return

    return utils.collect_task(domain, cfg, seed, srcdir=plan_dir, destdir=output_dir, copy_logs=False)


def main():
    args = parse_args()
    utils.setup_logging(args.debug)

    domain = DOMAINS[args.domain]
    generators_dir = Path(args.generators_dir)
    destdir = Path(args.destdir)
    tmp_dir = destdir / "tmp"

    # Build Configuration Space which defines all parameters and their ranges.
    cs = ConfigSpace.ConfigurationSpace()
    cs.add_hyperparameters(domain.attributes)
    print(f"Parameters: {cs.get_hyperparameters_dict()}")

    grid = generate_grid(cs)
    print(f"Number of configurations: {len(grid)}")
    if args.dry_run:
        return
    problem_names = []
    for cfg in grid:
        cfg = cfg.get_dictionary()
        for seed in range(args.num_random_seeds):
            problem_names.append(generate_task(
                generators_dir, domain, cfg, seed, tmp_dir, destdir,
                time_limit=args.generator_time_limit))
    shutil.rmtree(tmp_dir, ignore_errors=False)
    print([os.path.splitext(problem_name)[0] for problem_name in problem_names if problem_name is not None])


main()
