import math
from pathlib import Path
import shlex
import shutil
from string import Formatter
import subprocess
import sys

from ConfigSpace.hyperparameters import UniformIntegerHyperparameter
from ConfigSpace.hyperparameters import CategoricalHyperparameter


TMP_PROBLEM = "tmp-problem.pddl"
TMP_DOMAIN = "tmp-domain.pddl"
PRECISION = 0.1


class IllegalConfiguration(Exception):
    pass


def get_int(name, lower, upper, *, log=True):
    return UniformIntegerHyperparameter(
        name,
        lower=lower,
        upper=upper,
        default_value=lower,
        log=log
    )

def get_enum(name, choices, default_value):
    return CategoricalHyperparameter(name, choices, default_value=default_value)


class Domain:
    def __init__(
        self,
        name,
        generator_command,
        attributes,
        adapt_parameters=None
    ):
        self.name = name
        self.attributes = attributes
        self.command_template = generator_command
        self.adapt_parameters = adapt_parameters
        attribute_names = {a.name for a in self.attributes}
        attribute_names_in_command = {
            fn
            for _, fn, _, _ in Formatter().parse(self.command_template)
            if fn is not None and fn != "seed"
        }
        if attribute_names_in_command != attribute_names:
            sys.exit(
                f"Error: in domain {name} the attributes ({sorted(attribute_names)}) "
                f"don't match the generator command ({sorted(attribute_names_in_command)})")

    def get_domain_file(self, generators_dir):
        return Path(generators_dir) / self.name / "domain.pddl"

    def get_hyperparameters(self):
        return self.attributes

    def get_generator_command(self, generators_dir, parameters, seed):
        if self.adapt_parameters:
            parameters = self.adapt_parameters(parameters)
        command = shlex.split(self.command_template.format(seed=seed, **parameters))
        command[0] = str((Path(generators_dir) / self.name / command[0]).resolve())
        # Call Python scripts with the correct Python interpreter.
        if command[0].endswith(".py"):
            command.insert(0, sys.executable)
        return command

    def get_domain_filename(self, generators_dir):
        return (Path(generators_dir) / self.name / "domain.pddl").resolve()

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


def adapt_parameters_datanetwork(parameters):
    parameters["items"] = parameters["layers"] + parameters["extra_items"]
    parameters["scripts"] = (
        max(1, parameters["items"] - 2) + parameters["extra_scripts"]
    )
    return parameters


def adapt_parameters_logistics(parameters):
    parameters["num_trucks"] = parameters["num_cities"] + parameters["extra_trucks"]
    return parameters


def adapt_parameters_parking(parameters):
    curbs = parameters["curbs"]
    cars = 2 * (curbs - 1) + int(parameters["cars_diff"])
    return {"curbs": curbs, "cars": cars}


def adapt_parameters_storage(parameters):
    crates, hoists, store_areas, depots = (
        parameters["crates"],
        parameters["hoists"],
        parameters["store_areas"],
        parameters["depots"],
    )
    depots = min(depots, 36)
    parameters["depots"] = depots
    parameters["store_areas"] = store_areas + max(depots, hoists, crates)
    parameters["containers"] = math.ceil(crates / 4)

    return parameters


def adapt_parameters_snake(parameters):
    xgrid = int(parameters["x_grid"])
    ygrid = int(parameters["y_grid"])

    percentage = int(parameters["num_spawn_apples"][:-1]) / 100.0
    parameters["board"] = f"empty-{xgrid}x{ygrid}"

    if xgrid * ygrid * percentage < int(parameters["num_initial_apples"]):
        parameters["num_initial_apples"] = int(xgrid * ygrid * percentage)

    return parameters


def adapt_parameters_tetris(parameters):
    if parameters["rows"] % 2 == 1:
        raise IllegalConfiguration("number of rows must be even")
    return parameters


DOMAINS = [
    Domain(
        "blocksworld",
        "blocksworld 4 {n} {seed}",
        [get_int("n", lower=2, upper=100)],
    ),

    Domain("floortile",
           "floortile-generator.py name {rows} {columns} {robots} seq {seed}",
           [
            get_int("rows", lower=2, upper=10),
            get_int("columns", lower=2, upper=10),
            get_int("robots", lower=2, upper=10),
           ],
           adapt_parameters=adapt_parameters_floortile
    ),

    Domain(
        "mystery",
        "mystery -l {locations} -f {maxfuel} -s {maxspace} -v {vehicles} -c {cargos} -r {seed}",
        [get_int("locations", lower=2, upper=1000),
         get_int("maxfuel", lower=1, upper=1000),
         get_int("maxspace", lower=1, upper=1000),
         get_int("vehicles", lower=1, upper=1000),
         get_int("cargos", lower=1, upper=1000),
        ]),

    Domain(
        "tetris",
        "generator.py {rows} {block_type}",
        [get_int("rows", lower=4, upper=1000),
         get_enum("block_type", ["1", "2", "3", "4"], "1")],
         adapt_parameters=adapt_parameters_tetris,
    ),

    Domain(
        "tpp",
        "tpp -s {seed} -m {markets} -p {products} -t {trucks} -d {depots} -l {goods} " + TMP_PROBLEM,
        [get_int("products", lower=2, upper=20),
         get_int("markets", lower=1, upper=10),
         get_int("trucks", lower=2, upper=10),
         get_int("depots", lower=1, upper=10),
         get_int("goods", lower=3, upper=10)],
    ),
]


def get_domains():
    return {domain.name: domain for domain in DOMAINS}
