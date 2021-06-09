#! /usr/bin/env python3

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil

import utils


DIR = Path(__file__).resolve().parent
REPO = DIR.parent


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expdir", help="Experiment directory")
    parser.add_argument("destdir", help="Destination directory for benchmarks")
    return parser.parse_args()


def _compute_md5_hash(s):
    m = hashlib.md5()
    m.update(s.encode("utf-8"))
    return m.hexdigest()


def hash_task(plan_dir):
    with open(plan_dir / "problem.pddl") as f:
        content = f.read()
    return _compute_md5_hash(content)


def record_max_values(parameters, max_domain_values):
    for key, value in parameters.items():
        if key not in max_domain_values or value > max_domain_values[key]:
            max_domain_values[key] = value


def print_max_values(max_values):
    print("\nMax values:\n")
    for domain, max_values in sorted(max_values.items()):
        print(f" {domain}")
        for key, value in sorted(max_values.items()):
            print(f"  {key}: {value}")
        print()


def main():
    args = parse_args()
    expdir = Path(args.expdir)
    destdir = Path(args.destdir)
    plan_dirs = expdir.glob("runs-*-*/*/smac-*/run_*/plan/*/*/")
    max_values = defaultdict(dict)
    seen_task_hashes = defaultdict(set)
    for plan_dir in plan_dirs:
        try:
            with open(plan_dir / "properties.json") as f:
                props = json.load(f)
        except FileNotFoundError:
            continue
        if props["planner_exitcode"] != 0:
            continue
        print(f"Found {props}")
        domain = props["domain"]

        # Skip duplicate tasks.
        hash = hash_task(plan_dir)
        if hash in seen_task_hashes[domain]:
            print("Skip duplicate task")
            continue
        else:
            seen_task_hashes[domain].add(hash)

        values = props["parameters"].copy()
        values["planner_runtime"] = props["runtime"]
        record_max_values(values, max_values[domain])
        parameters = utils.join_parameters(props["parameters"])
        seed = props["seed"]
        problem_name = f"p-{parameters}-{seed}.pddl"
        target_dir = destdir / domain
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan_dir / "problem.pddl", target_dir / problem_name)

        # Write domain file and information about parameters.
        shutil.copy2(plan_dir / "domain.pddl", target_dir)
        order = ", ".join(str(k) for k in sorted(props["parameters"]))
        with open(target_dir / "README", "w") as f:
            print(f"Parameter order: {order}", file=f)

    print_max_values(max_values)


main()
