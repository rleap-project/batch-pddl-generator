import math
from pathlib import Path
import shlex
import shutil
from string import Formatter
import subprocess
import sys

from ConfigSpace.hyperparameters import UniformFloatHyperparameter
from ConfigSpace.hyperparameters import UniformIntegerHyperparameter as Int
from ConfigSpace.hyperparameters import CategoricalHyperparameter

TMP_PROBLEM = "tmp-problem.pddl"
TMP_DOMAIN = "tmp-domain.pddl"
PRECISION = 0.1


class IntegerParameter:
    def __init__(self, name, lower_b=1, upper_b=20, upper_m=5.0, log=True):
        self.name = name
        self.min = lower_b
        self.max = upper_b + 30 * upper_m
        self.default = lower_b
        self.log = log

    def get_hyperparameters(self):
        return Int(
            f"{self.name}",
            lower=self.min,
            upper=self.max,
            default_value=self.default,
            log=self.log,
        )


def get_int(name, lower, upper, *, log=True):
    return Int(
        name,
        lower=lower,
        upper=upper,
        default_value=lower,
        log=log
    )

def get_enum(name, choices, default_value):
    return CategoricalHyperparameter(name, choices, default_value=default_value)

class GridAttr:
    def __init__(
        self,
        name,
        name_x,
        name_y,
        lower_x,
        upper_x,
        lower_m=0.1,
        upper_m=3.0,
        default_m=1.0,
        level="false",
    ):
        self.name = name
        self.name_x = name_x
        self.name_y = name_y

        self.lower_m = lower_m
        self.upper_m = upper_m
        self.default_m = default_m

        self.lower_x = lower_x
        self.upper_x = upper_x
        self.level_enum = level

        assert self.level_enum in ["false", "true", "choose"]

    def get_level_enum(self, cfg):
        if self.level_enum == "choose":
            return cfg[f"{self.name}_level"]
        else:
            return self.level_enum

    def has_lowest_value(self, cfg):
        return self.lower_x == cfg[f"{self.name}_x"]

    def get_hyperparameters(self, modifier=None):
        attr = f"{modifier}_{self.name}" if modifier else self.name

        H = [
            UniformIntegerHyperparameter(
                f"{attr}_x",
                lower=self.lower_x,
                upper=self.upper_x,
                default_value=self.lower_x,
            ),
            UniformIntegerHyperparameter(
                f"{attr}_maxdiff", lower=0, upper=5, default_value=3
            ),
            UniformFloatHyperparameter(
                f"{attr}_m",
                lower=self.lower_m,
                upper=self.upper_m,
                default_value=self.default_m,
                q=PRECISION,
            ),
        ]

        if self.level_enum == "choose":
            assert (
                modifier is None
            )  # It does not make sense to have enum parameters and hierarchical linear attributes
            H.append(
                CategoricalHyperparameter(
                    f"{attr}_level", ["true", "false"], default_value="false"
                )
            )

        return H

    def set_values(self, cfg, Y):
        attr = self.name

        val_x = (
            self.lower_x if self.lower_x == self.upper_x else int(cfg.get(f"{attr}_x"))
        )
        m = float(cfg.get(f"{attr}_m"))
        maxdiff = (
            self.lower_x
            if self.lower_x == self.upper_x
            else int(cfg.get(f"{attr}_maxdiff"))
        )
        grid_values = []
        for i in range(len(Y) * int(math.ceil(1 + m) + 2)):
            for j in range(maxdiff + 1):
                x = val_x + i
                y = val_x + i + j
                grid_values.append((x, y))

        sorted_values = sorted(grid_values, key=lambda x: x[0] * x[1])

        val = 0.0

        for i, Yi in enumerate(Y):
            Yi[self.name_x] = sorted_values[int(val)][0]
            Yi[self.name_y] = sorted_values[int(val)][1]

            val += m


class ConstantAttr:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def get_hyperparameters(self, modifier=None):
        return []

    def get_level_enum(self, cfg):
        return "false"

    def set_values(self, cfg, Y):
        for i, Yi in enumerate(Y):
            Yi[self.name] = self.value

    def has_lowest_value(self, cfg):
        return True


class EnumAttr:
    def __init__(self, name, values):
        self.values = values
        self.name = name

    def get_hyperparameters(self):
        return [CategoricalHyperparameter(self.name, self.values)]

    def get_level_enum(self, cfg):
        return "false"

    def set_values(self, cfg, Y):
        value = cfg.get(self.name)
        for i, Yi in enumerate(Y):
            Yi[self.name] = value

    def get_values(self):
        return self.values


def eliminate_duplicates(l):
    seen = set()
    seen_add = seen.add
    return [
        x for x in l if not (tuple(x.items()) in seen or seen_add(tuple(x.items())))
    ]


# Scale linear attributes, ensuring that all instances have different values.
def get_linear_scaling_values(linear_attrs, cfg, num_tasks):
    assert linear_attrs
    num_generated = num_tasks

    # Attempt this 20 times, each time generating twice as many configurations.
    for _ in range(20):
        result = [{} for _ in range(num_generated)]
        for attr in linear_attrs:
            attr.set_values(cfg, result)

        result = eliminate_duplicates(result)

        if len(result) >= num_tasks:
            return result[:num_tasks]

        num_generated *= 2

    print("Warning: we cannot generate different attributes", cfg, linear_attrs)

    result = [{} for _ in range(num_tasks)]
    for attr in linear_attrs:
        attr.set_values(cfg, result)
    return result


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
        generator_attribute_names = {
            fn
            for _, fn, _, _ in Formatter().parse(self.command_template)
            if fn is not None and fn != "seed"
        }
        if generator_attribute_names != set(param.name for param in self.attributes):
            sys.exit(f"Error: in domain {name} the attributes don't match the generator command")

    def get_domain_file(self, generators_dir):
        return Path(generators_dir) / self.name / "domain.pddl"

    def get_hyperparameters(self):
        return self.attributes

    def get_generator_command(self, generators_dir, parameters, seed):
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
    parameters["num_robots"] = min(parameters["num_robots"], parameters["num_columns"])
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


DOMAINS = [
    Domain(
        "blocksworld",
        "blocksworld 4 {n} {seed}",
        [Int("n", lower=2, upper=100, default_value=2)],
    ),

    Domain(
        "tetris",
        "generator.py {rows} {block_type}",
        [get_int("rows", lower=4, upper=1000),
         get_enum("block_type", ["1", "2", "3", "4"], "1")],
    ),

    #Domain("floortile",
    #       "floortile-generator.py name {num_rows} {num_columns} {num_robots} seq {seed}",
    #       [GridAttr("grid", "num_columns", "num_rows", lower_x=2, upper_x=10, upper_m=10),
    #        EnumAttr("num_robots", [2, 3, 4, 5])
    #       ], adapt_parameters=adapt_parameters_floortile
    #),
]


def get_domains():
    return {domain.name: domain for domain in DOMAINS}
