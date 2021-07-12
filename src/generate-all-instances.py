#! /usr/bin/env python3

import argparse
import logging
from pathlib import Path
import shutil
import subprocess

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


def generate_task(generators_dir, domain, cfg, seed, tmp_dir, output_dir):
    try:
        cfg = domain.adapt_parameters(cfg)
    except domains.IllegalConfiguration as err:
        logging.warning(f"Skipping illegal configuration {cfg}: {err}")
        return

    logging.info(f"Create instance for configuration {cfg} with seed {seed}")
    try:
        plan_dir = utils.generate_input_files(generators_dir, domain, cfg, seed, tmp_dir, timeout=1)
    except subprocess.CalledProcessError as err:
        logging.error(f"Failed to generate task: {err}")
        raise
    except subprocess.TimeoutExpired as err:
        logging.error(f"Failed to generate task: {err}")
        return

    utils.collect_task(domain, cfg, seed, srcdir=plan_dir, destdir=output_dir, copy_logs=False)


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
    for cfg in grid:
        cfg = cfg.get_dictionary()
        for seed in range(args.num_random_seeds):
            generate_task(generators_dir, domain, cfg, seed, tmp_dir, destdir)
    shutil.rmtree(tmp_dir, ignore_errors=False)


main()