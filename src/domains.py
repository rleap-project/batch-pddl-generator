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


def get_int(name, lower, upper, *, log=False, step_size=1):
    return UniformIntegerHyperparameter(
        name, lower=lower, upper=upper, default_value=lower, log=log, q=step_size
    )


def get_float(name, lower, upper, *, log=False, precision=0.01):
    return UniformFloatHyperparameter(
        name, lower=lower, upper=upper, default_value=lower, log=log, q=precision
    )


def get_enum(name, choices, default_value=None):
    if default_value is None:
        default_value = choices[0]
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
            parameters = self._adapt_parameters(parameters.copy())
        return parameters

    def get_generator_command(self, generators_dir, parameters, seed):
        command = shlex.split(self.command_template.format(seed=seed, **parameters))
        command[0] = str((Path(generators_dir) / self.name / command[0]).resolve())
        # Call Python scripts with the correct Python interpreter.
        if command[0].endswith(".py"):
            command.insert(0, sys.executable)
        return command

    def generate_problem(self, command, problem_file, domain_file, timeout=None):
        # Some generators print to a file, others print to stdout.
        if TMP_PROBLEM in self.command_template:
            subprocess.run(command, check=True, timeout=timeout)
            shutil.move(TMP_PROBLEM, problem_file)
        else:
            with open(problem_file, "w") as f:
                subprocess.run(command, stdout=f, check=True, timeout=timeout)

        if self.uses_per_instance_domain_file():
            shutil.move(TMP_DOMAIN, domain_file)

    def uses_per_instance_domain_file(self):
        return TMP_DOMAIN in self.command_template


def adapt_parameters_barman(parameters):
    if parameters["shots"] < parameters["cocktails"]:
        raise IllegalConfiguration("we need shots >= cocktails")
    return parameters


def adapt_parameters_floortile(parameters):
    parameters["robots"] = min(parameters["robots"], parameters["columns"])
    return parameters


def adapt_parameters_freecell(parameters):
    if parameters["initial_stacks"] > parameters["columns"]:
        raise IllegalConfiguration("we need initial_stacks <= columns")
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


def adapt_parameters_tetris(parameters):
    if parameters["rows"] % 2 == 1:
        raise IllegalConfiguration("number of rows must be even")
    return parameters


def adapt_parameters_tidybot(parameters):
    if parameters["mintablesize"] > parameters["maxtablesize"]:
        raise IllegalConfiguration("mintablesize must be <= maxtablesize")
    return parameters


"""
Max parameter values:

 agricola (5h)
  planner_runtime: 17637.6
  stages: 12 (3-12)
  workers: 13 (3-15)

  Runtime smaller than:
   5s: 6, 10s: 507, 20s: 199, 50s: 446, 100s: 263, 200s: 236, 500s: 333, 1000s: 39, 2000s: 25, 5000s: 4, 10000s: 4, infs: 6

 mystery (limits=1K, 2h)
  cargos: 244
  locations: 679
  maxfuel: 996
  maxspace: 964
  vehicles: 980

 mystery (limits=100K, 5h)
  cargos: 794
  locations: 342
  maxfuel: 9984
  maxspace: 9968
  planner_runtime: 8912.78
  vehicles: 6943

  Runtime smaller than
   1s: 6697, 10s: 5867, 20s: 1327, 50s: 1700, 100s: 1259, 200s: 1085, 500s: 882, 1000s: 161, 2000s: 12, 5000s: 3, 10000s: 5

 tetris (5h)
  block_type: 4
  rows: 272 (4-1000)

  Runtime smaller than:
   1s: 3634, 2s: 1332, 5s: 1954, 10s: 625, 20s: 620, 50s: 463, 100s: 131, 200s: 49, 500s: 31, 1000s: 8, 2000s: 4, 5000s: 1


Hard tasks (SMAC4HPO):

agricola
  all_workers_flag: --must_create_workers
  planner_runtime: 16734.25
  stages: 12
  workers: 13

 mystery
  cargos: 235
  locations: 34
  maxfuel: 5975
  maxspace: 9551
  planner_runtime: 4688.43
  vehicles: 7

 pathways
  goals: 981
  planner_runtime: 1397.82
  reactions: 9800
  substances: 998

 tetris
  block_type: 4
  planner_runtime: 2049.34
  rows: 14

Tasks:
 agricola: 6610
 mystery: 8584
 pathways: 49470
 tetris: 1695

Runtime smaller than:
 agricola: 5s: 46, 10s: 146, 20s: 1448, 50s: 3131, 100s: 606, 200s: 637, 500s: 499, 1000s: 52, 2000s: 25, 5000s: 4, 10000s: 9, infs: 7
 mystery: 1s: 559, 2s: 706, 5s: 997, 10s: 342, 20s: 708, 50s: 342, 100s: 1222, 200s: 1420, 500s: 1562, 1000s: 665, 2000s: 59, 5000s: 2
 pathways: 1s: 891, 2s: 5000, 5s: 16102, 10s: 12278, 20s: 9984, 50s: 2177, 100s: 64, 200s: 2891, 500s: 82, 2000s: 1
 tetris: 1s: 324, 2s: 103, 5s: 339, 10s: 369, 20s: 209, 50s: 192, 100s: 103, 200s: 41, 500s: 11, 1000s: 2, 2000s: 1, 5000s: 1


Hard Tasks (SMAC4AC, deterministic, fewer parallel runs)

Max values:

 agricola
  all_workers_flag: --must_create_workers
  planner_runtime: 10333.44
  stages: 12
  workers: 13

 mystery
  cargos: 336
  locations: 168
  maxfuel: 9977
  maxspace: 5121
  planner_runtime: 6385.7
  vehicles: 1102

 pathways
  goals: 8653
  planner_runtime: 9076.46
  reactions: 916910
  substances: 2264

 tetris
  block_type: 4
  planner_runtime: 1603.09
  rows: 138

Tasks:
 agricola: 67
 mystery: 492
 pathways: 114
 tetris: 42

Runtime smaller than:
 agricola: 5s: 2, 10s: 7, 20s: 13, 50s: 14, 100s: 11, 200s: 9, 500s: 7, 2000s: 1, 10000s: 2, infs: 1
 mystery: 1s: 16, 2s: 8, 5s: 14, 10s: 14, 20s: 6, 50s: 23, 100s: 35, 200s: 34, 500s: 182, 1000s: 159, 10000s: 1
 pathways: 1s: 17, 2s: 7, 5s: 10, 10s: 5, 20s: 6, 50s: 5, 100s: 2, 200s: 6, 500s: 9, 1000s: 2, 2000s: 2, 5000s: 29, 10000s: 14
 tetris: 1s: 5, 2s: 8, 5s: 3, 10s: 4, 20s: 4, 50s: 6, 100s: 4, 200s: 3, 500s: 2, 1000s: 2, 2000s: 1
"""
DOMAINS = [
    Domain(
        "agricola",
        "GenAgricola.py {stages} {seed} --num_workers {workers} {all_workers_flag}",
        # Exclude --num_ints and --num_rounds {num_rounds} because they were not used in IPC'18.
        [
            get_int("stages", lower=3, upper=20),
            get_int("workers", lower=3, upper=20),
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
        adapt_parameters=adapt_parameters_barman,
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
        "freecell",
        "freecell -f {cells} -c {columns} -s 4 -0 {suite_size} -1 {suite_size} "
        "-2 {suite_size} -3 {suite_size} -i {initial_stacks} -r {seed}",
        [
            get_int("cells", lower=2, upper=4),
            get_int("columns", lower=3, upper=8),
            #get_int("suits", lower=4, upper=4),  # hardcoded as in IPC tasks
            get_int("suite_size", lower=2, upper=20),
            get_int("initial_stacks", lower=1, upper=8),
        ],
        adapt_parameters=adapt_parameters_freecell,
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
        "mprime",
        "mprime -l {locations} -f {maxfuel} -s {maxspace} -v {vehicles} -c {cargos} -r {seed}",
        [
            # optimal planning (ranges from IPC renamed domain version):
            #   for file in `ls prob*.pddl`; do grep location $file | wc -l; done | sort -n | uniq | paste -s -d,
            #get_int("locations", lower=4, upper=22, step_size=1),  # 4,5,6,7,8,10,11,12,13,15,16,17,18,19,21,22
            #get_int("maxfuel", lower=3, upper=13, step_size=1),  # 3,4,5,6,7,8,9,10,11,12,13
            #get_int("maxspace", lower=1, upper=3, step_size=1),  # 1,2,3
            #get_int("vehicles", lower=1, upper=16, step_size=1),  # 1,2,3,4,5,6,7,8,9,11,16
            #get_int("cargos", lower=2, upper=46, step_size=1),  # 2,3,4,5,6,7,8,9,10,11,13,14,15,16,18,20,22,24,34,37,39,40,44,46
            get_enum("locations", [3,4,5,6,8,10]),
            get_enum("maxfuel", [3,4,5,6,8,10]),
            get_enum("maxspace", [1,2,3]),
            get_enum("vehicles", [1,2,3,4,6,8]),
            get_enum("cargos", [1,2,3,4,5,6,8,10,12]),
            # satisficing planning
            #get_int("locations", lower=5, upper=25, step_size=5),
            #get_int("maxfuel", lower=10, upper=15, step_size=5),
            #get_int("maxspace", lower=2, upper=4, step_size=2),
            #get_int("vehicles", lower=2, upper=16, step_size=2),
            #get_int("cargos", lower=5, upper=50, step_size=5),
        ],
    ),
    Domain(
        "mystery",
        "mystery -l {locations} -f {maxfuel} -s {maxspace} -v {vehicles} -c {cargos} -r {seed}",
        [
            get_int("locations", lower=5, upper=25, step_size=5),
            get_int("maxfuel", lower=10, upper=15, step_size=5),
            get_int("maxspace", lower=2, upper=4, step_size=2),
            get_int("vehicles", lower=2, upper=16, step_size=2),
            get_int("cargos", lower=5, upper=50, step_size=5),
        ],
    ),
    Domain(
        "pathways",
        f"wrapper.py --seed {{seed}} --reactions {{reactions}} --goals {{goals}} --initial-substances {{substances}} {TMP_DOMAIN} {TMP_PROBLEM}",
        [
            # optimal planning
            #get_int("reactions", lower=1, upper=101, step_size=5),  # IPC: 12-480
            #get_int("goals", lower=1, upper=31, step_size=3),  # IPC: 1-40
            #get_int("substances", lower=1, upper=22, step_size=3),  # IPC: 3-35
            # satisficing planning
            get_int("reactions", lower=10, upper=1010, step_size=50),  # IPC: 12-480
            get_int("goals", lower=10, upper=90, step_size=10),  # IPC: 1-40
            get_int("substances", lower=10, upper=80, step_size=10),  # IPC: 3-35
        ],
    ),
    Domain(
        "tetris",
        "generator.py {rows} {block_type} {seed}",
        [
            get_int("rows", lower=4, upper=50),
            get_enum("block_type", ["1", "2", "3", "4"], "1"),
        ],
        adapt_parameters=adapt_parameters_tetris,
    ),
    Domain(
        "tidybot",
        "gentidy.py {worldsize} {tables} {cupboards} {mintablesize} {maxtablesize} {cupboardsize} {seed}",
        [
            get_int("worldsize", lower=5, upper=15, step_size=1),  # IPC 2011: 5-9 (opt), 9-12 (sat)
            get_int("tables", lower=0, upper=10, step_size=2),  # IPC 2011: 0-5 (opt), 2-9 (sat)
            get_int("cupboards", lower=1, upper=3),  # IPC 2011: 1 (opt), 1-3 (sat)
            get_int("mintablesize", lower=1, upper=5, step_size=2),  # IPC 2011: ? (opt), ? (sat)
            get_int("maxtablesize", lower=1, upper=5, step_size=2),  # IPC 2011: ? (opt), ? (sat)
            get_int("cupboardsize", lower=4, upper=5),  # IPC 2011: ? (opt), ? (sat), 4 (README)
        ],
        adapt_parameters=adapt_parameters_tidybot,
    ),
    # Schedule
    #
    # -p <num>    number of parts (minimal 1)
    # -s <num>    number of shapes (preset: 0, maximal: 2)
    # -c <num>    number of colors (preset: 2, minimal 1, maximal: 4)
    # -w <num>    number of widths (preset: 2, minimal 1, maximal: 3)
    # -o <num>    number of orientations (preset: 2, minimal 1, maximal: 2)
    # -Q <num>    probability cylindrical goal (preset: 80)
    # -W <num>    probability of colour in I (preset: 50)
    # -E <num>    probability of colour in G (preset: 80)
    # -R <num>    probability of hole in I (preset: 50)
    # -T <num>    probability of hole in G (preset: 80)
    # -Y <num>    probability of surface condition in G (preset: 50)
    # -r <num>    random seed (minimal 1, optional)
    Domain(
        "schedule",
        "./schedule "
        "-p {parts} -s {shapes} -c {colors} -w {widths} -o {orientations} "
        "-Q {prob_cylindrical_goal} -W {prob_color_init} -E {prob_color_goal} "
        "-R {prob_hole_init} -T {prob_hole_goal} -Y {prob_surface_goal} -r {seed}",
        [
            get_int("parts", lower=1, upper=100),
            get_int("shapes", lower=0, upper=2, log=False),
            get_int("colors", lower=1, upper=4, log=False),
            get_int("widths", lower=1, upper=3, log=False),
            get_int("orientations", lower=1, upper=2, log=False),
            get_int("prob_cylindrical_goal", lower=0, upper=100, log=False),
            get_int("prob_color_init", lower=0, upper=100, log=False),
            get_int("prob_color_goal", lower=0, upper=100, log=False),
            get_int("prob_hole_init", lower=0, upper=100, log=False),
            get_int("prob_hole_goal", lower=0, upper=100, log=False),
            get_int("prob_surface_goal", lower=0, upper=100, log=False),
        ],
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
