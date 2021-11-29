#! /usr/bin/env python3

"""Find duplicate PDDL instances."""

import argparse
from collections import defaultdict
from pathlib import Path
import shlex
from subprocess import check_output


def compute_md5(f):
    output = check_output(["md5sum", f]).decode("utf-8")
    md5 = output.split(" ")[0]
    return md5


def find_tasks(paths):
    for path in paths:
        path = Path(path)
        if path.is_file() and path.suffix == ".pddl" and not "domain" in path.name:
            yield Task(path)
        elif path.is_dir():
            yield from find_tasks(list(path.iterdir()))


def find_file(filenames, dir: Path):
    for filename in filenames:
        path = dir / filename
        if path.is_file():
            return path
    raise OSError(f"none found in {dir!r}: {filenames!r}")


def find_domain_file(task_path: Path):
    domain_basenames = [
        "domain.pddl",
        task_path.stem + "-domain" + task_path.suffix,
        task_path.stem[:3] + "-domain.pddl",  # for airport and psr-small
        "domain_" + task_path.name,
        "domain-" + task_path.name,
    ]
    return find_file(domain_basenames, task_path.parent)


class Task:
    def __init__(self, path):
        self.task_file = path
        self.domain_file = find_domain_file(path)
        self.hash = compute_md5(self.task_file)
        if self.domain_file:
            self.hash += compute_md5(self.domain_file)

    def __hash__(self):
        return self.hash

    def __lt__(self, other):
        return self.task_file < other.task_file

    def __le__(self, other):
        return self.task_file <= other.task_file

    def __repr__(self):
        return str(self)

    def __str__(self):
        return f"<Task {self.task_file}>"


def get_equivalent_problems(problems):
    equivalent_problems = defaultdict(list)
    for problem in problems:
        equivalent_problems[problem.hash].append(problem)
    return equivalent_problems.values()


def print_duplicates(equivalence_partition):
    print("Duplicates:\n")
    to_delete = []
    for partition in equivalence_partition:
        if len(partition) > 1:
            to_delete.extend(sorted(partition)[1:])
            for task in sorted(partition):
                try:
                    relpath = task.task_file.relative_to(Path.cwd())
                except ValueError:
                    relpath = task.task_file
                print(f"{relpath}")
            print()

    if to_delete:
        print("Delete the following files to only keep the first task of each class:")
        cmd = []
        for task in to_delete:
            cmd.append(f"{task.task_file}")
            if task.domain_file.name != "domain.pddl":
                cmd.append(f"{task.domain_file.name}")
        print(shlex.join(cmd))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        help="one or more paths to PDDL files or directories containing PDDL files",
    )
    args = parser.parse_args()

    tasks = list(find_tasks(args.paths))
    print(f"Found {len(tasks)} tasks")
    equivalence_partition = get_equivalent_problems(tasks)
    print_duplicates(equivalence_partition)


main()
