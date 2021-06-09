from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from ConfigSpace.hyperparameters import CategoricalHyperparameter
from ConfigSpace.hyperparameters import UniformFloatHyperparameter
from ConfigSpace.hyperparameters import UniformIntegerHyperparameter


TMP_PROBLEM = "tmp-problem.pddl"
TMP_DOMAIN = "tmp-domain.pddl"


class IllegalConfiguration(Exception):
    pass


def get_int(name, lower, upper, *, log=True):
    return UniformIntegerHyperparameter(
        name, lower=lower, upper=upper, default_value=lower, log=log
    )


def get_float(name, lower, upper, *, log=False, precision=0.01):
    return UniformFloatHyperparameter(
        name, lower=lower, upper=upper, default_value=lower, log=log, q=precision
    )


def get_enum(name, choices, default_value):
    return CategoricalHyperparameter(name, choices, default_value=default_value)


class Domain:
    def __init__(self, name, generator_command, attributes, adapt_parameters=None):
        self.name = name
        self.attributes = attributes
        self.command_template = generator_command
        self._adapt_parameters = adapt_parameters

    def get_domain_file(self, generators_dir):
        return Path(generators_dir) / self.name / "domain.pddl"

    def adapt_parameters(self, parameters):
        if self._adapt_parameters:
            parameters = self._adapt_parameters(parameters)
        return parameters

    def get_generator_command(self, generators_dir, parameters, seed):
        command = shlex.split(self.command_template.format(seed=seed, **parameters))
        command[0] = str((Path(generators_dir) / self.name / command[0]).resolve())
        # Call Python scripts with the correct Python interpreter.
        if command[0].endswith(".py"):
            command.insert(0, sys.executable)
        return command

    def generate_problem(self, command, problem_file, domain_file):
        # Some generators print to a file, others print to stdout.
        if TMP_PROBLEM in self.command_template:
            subprocess.run(command, check=True)
            shutil.move(TMP_PROBLEM, problem_file)
        else:
            with open(problem_file, "w") as f:
                subprocess.run(command, stdout=f, check=True)

        if self.uses_per_instance_domain_file():
            shutil.move(TMP_DOMAIN, domain_file)

    def uses_per_instance_domain_file(self):
        return TMP_DOMAIN in self.command_template


def adapt_parameters_floortile(parameters):
    parameters["robots"] = min(parameters["robots"], parameters["columns"])
    return parameters


def adapt_parameters_grid(parameters):
    parameters["shapes"] = min(
        parameters["x"] * parameters["y"] - 1, parameters["shapes"]
    )
    parameters["keys"] = min(
        parameters["x"] * parameters["y"] - 1,
        parameters["shapes"] + parameters["extra_keys"],
    )
    parameters["locks"] = int(
        parameters["x"] * parameters["y"] * parameters["percentage_cells_locked"]
    )
    parameters["locks"] = max(parameters["locks"], parameters["shapes"])
    return parameters


def adapt_parameters_parking(parameters):
    curbs = parameters["curbs"]
    cars = 2 * (curbs - 1) + int(parameters["cars_diff"])
    return {"curbs": curbs, "cars": cars}


def adapt_parameters_tetris(parameters):
    if parameters["rows"] % 2 == 1:
        raise IllegalConfiguration("number of rows must be even")
    return parameters


"""
Max parameter values after first optimization (2h):

 mystery (limits=1000)
  cargos: 244
  locations: 679
  maxfuel: 996
  maxspace: 964
  vehicles: 980

 tetris
  block_type: 4
  rows: 272/1000
"""
DOMAINS = [
    Domain(
        "agricola",
        "GenAgricola.py {stages} {seed} --num_workers {workers} {all_workers_flag}",
        # Exclude --num_ints and --num_rounds {num_rounds} because they were not used in IPC'18.
        [
            get_int("stages", lower=3, upper=12),
            get_int("workers", lower=3, upper=15),
            get_enum(
                "all_workers_flag", ["", "--must_create_workers"], default_value=""
            ),
        ],
    ),
    Domain(
        "barman",
        "barman-generator.py {cocktails} {ingredients} {shots} {seed}",
        [
            get_int("cocktails", lower=1, upper=10),
            get_int("shots", lower=1, upper=5),
            get_int("ingredients", lower=2, upper=6),
        ],
    ),
    Domain(
        "blocksworld",
        "blocksworld 4 {n} {seed}",
        [get_int("n", lower=2, upper=100)],
    ),
    Domain(
        "childsnack",
        "child-snack-generator.py pool {seed} {children} {trays} {gluten_factor} {constrainedness}",
        [
            get_int("children", lower=2, upper=100),
            get_float("constrainedness", lower=1.0, upper=2.0),
            get_int("trays", lower=2, upper=4),
            get_float("gluten_factor", lower=0.4, upper=0.8),
        ],
    ),
    Domain(
        "driverlog",
        "dlgen {seed} {roadjunctions} {drivers} {packages} {trucks}",
        [
            get_int("drivers", lower=1, upper=100),
            get_int("packages", lower=1, upper=100),
            get_int("roadjunctions", lower=2, upper=100),
            get_int("trucks", lower=1, upper=100),
        ],
    ),
    Domain(
        "floortile",
        "floortile-generator.py name {rows} {columns} {robots} seq {seed}",
        [
            get_int("rows", lower=2, upper=10),
            get_int("columns", lower=2, upper=10),
            get_int("robots", lower=2, upper=10),
        ],
        adapt_parameters=adapt_parameters_floortile,
    ),
    Domain(
        "grid",
        "generate.py {x} {y} --shapes {shapes} --keys {keys} --locks {locks} --prob-goal {prob_key_in_goal} --seed {seed}",
        [
            get_int("x", lower=3, upper=100),
            get_int("y", lower=3, upper=100),
            get_float("prob_key_in_goal", lower=0.5, upper=1.0),
            get_int("shapes", lower=1, upper=100),
            get_int("extra_keys", lower=1, upper=100),
            get_float("percentage_cells_locked", lower=0.1, upper=0.9),
        ],
        adapt_parameters=adapt_parameters_grid,
    ),
    Domain(
        "mystery",
        "mystery -l {locations} -f {maxfuel} -s {maxspace} -v {vehicles} -c {cargos} -r {seed}",
        [
            get_int("locations", lower=2, upper=10 ** 5),
            get_int("maxfuel", lower=1, upper=10 ** 5),
            get_int("maxspace", lower=1, upper=10 ** 5),
            get_int("vehicles", lower=1, upper=10 ** 5),
            get_int("cargos", lower=1, upper=10 ** 5),
        ],
    ),
    Domain(
        "tetris",
        "generator.py {rows} {block_type}",
        [
            get_int("rows", lower=4, upper=1000),
            get_enum("block_type", ["1", "2", "3", "4"], "1"),
        ],
        adapt_parameters=adapt_parameters_tetris,
    ),
    Domain(
        "tpp",
        "tpp -s {seed} -m {markets} -p {products} -t {trucks} -d {depots} -l {goods} "
        + TMP_PROBLEM,
        [
            get_int("products", lower=2, upper=20),
            get_int("markets", lower=1, upper=10),
            get_int("trucks", lower=2, upper=10),
            get_int("depots", lower=1, upper=10),
            get_int("goods", lower=3, upper=10),
        ],
    ),
]


def get_domains():
    return {domain.name: domain for domain in DOMAINS}
