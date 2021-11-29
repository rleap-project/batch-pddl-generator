#! /usr/bin/env python3

"""Parse input task into PDDL model and compute hash representation for it."""

import io
import hashlib
import os
from pathlib import Path
import sys

DIR = Path(__file__).resolve().parent
REPO = DIR.parent

DOWNWARD_DIR = Path(os.environ["DOWNWARD_REPO"])
TRANSLATOR_DIR = DOWNWARD_DIR / "src" / "translate"

sys.path.insert(0, str(TRANSLATOR_DIR))

from pddl_parser import pddl_file
import pddl


def dump_task(task):
    temp_out = io.StringIO()
    sys.stdout = temp_out

    # print(f"Domain: {task.domain_name}")
    # print(f"Task: {task.task_name}")
    # print(f"Requirements: {sorted(task.requirements.requirements)}")
    print(f"Types: {sorted(repr(typ) for typ in task.types)}")
    print(f"Objects: {sorted(str(obj) for obj in task.objects)}")
    print("Predicates:")
    for pred in task.predicates:
        print(f"  {pred}")
    print("Functions:")
    for func in sorted(str(f) for f in task.functions):
        print(f"  {func}")
    print("Init:")
    for fact in sorted(str(f) for f in task.init):
        print(f"  {fact}")
    print("Goal:")
    if isinstance(task.goal, pddl.Atom):
        print(f"  {task.goal}")
    else:
        for atom in sorted(str(p) for p in task.goal.parts):
            print(f"  {atom}")
    # TODO: sort conditions in actions and axioms.
    print("Actions:")
    for action in sorted(task.actions, key=lambda a: a.name):
        action.dump()
    if task.axioms:
        print("Axioms:")
        for axiom in sorted(task.axioms, key=lambda a: a.name):
            axiom.dump()

    sys.stdout = sys.__stdout__

    return temp_out.getvalue()


def main():
    task = pddl_file.open()
    task_string = dump_task(task)
    debug = False
    if debug:
        print(task_string)
    m = hashlib.md5()
    m.update(task_string.encode("utf-8"))
    print(m.hexdigest())


main()
