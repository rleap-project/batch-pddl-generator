"""
Classes and functions for running paper experiments with Fast Downward.
"""

from collections import defaultdict, namedtuple
import getpass
import os
import os.path
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

import parse

from lab.environments import LocalEnvironment, BaselSlurmEnvironment
from lab.experiment import Experiment, ARGPARSER
from lab.reports import Attribute, geometric_mean
from lab.reports.filter import FilterReport
from lab import tools

from downward.experiment import FastDownwardExperiment
from downward.reports.absolute import AbsoluteReport
from downward.reports.compare import ComparativeReport
from downward.reports.taskwise import TaskwiseReport
from downward import suites


DIR = Path(__file__).resolve().parent
REPO = DIR.parent
IMAGES_DIR = REPO / "images"
NODE = platform.node()
REMOTE = NODE.endswith((".scicore.unibas.ch", ".cluster.bc2.ch"))

User = namedtuple("User", ["email", "scp_login", "remote_user", "repos"])

USERS = {
    "jendrik": User(
        email=None,
        scp_login="seipp@login-infai.scicore.unibas.ch",
        remote_user="seipp",
        repos="/home/jendrik/projects/Downward"),
    "seipp": User(
        email="jendrik.seipp@unibas.ch",
        scp_login=None,
        remote_user=None,
        repos="/infai/seipp/projects"),
}
LOGIN = getpass.getuser()
USER = USERS[LOGIN]
REMOTE_USER = USERS.get(USER.remote_user)

ARGPARSER.add_argument("--tex", action="store_true", help="produce tex output")
ARGPARSER.add_argument("--relative", action="store_true", help="produce relative scatter plot")
ARGPARSER.add_argument("--test", action="store_true", help="test experiment locally", default=not REMOTE)
args = ARGPARSER.parse_args()
TEX = args.tex
RELATIVE = args.relative
TEST = args.test

EVALUATIONS_PER_TIME = Attribute(
    "evaluations_per_time", min_wins=False, function=geometric_mean, digits=1)

BENCHMARKS_DIR = os.environ["DOWNWARD_BENCHMARKS"]

SUITE_OPTIMAL = [
    'agricola-opt18-strips', 'airport', 'barman-opt11-strips',
    'barman-opt14-strips', 'blocks', 'childsnack-opt14-strips',
    'data-network-opt18-strips', 'depot', 'driverlog',
    'elevators-opt08-strips', 'elevators-opt11-strips',
    'floortile-opt11-strips', 'floortile-opt14-strips', 'freecell',
    'ged-opt14-strips', 'grid', 'gripper', 'hiking-opt14-strips',
    'logistics00', 'logistics98', 'miconic', 'movie', 'mprime',
    'mystery', 'nomystery-opt11-strips', 'openstacks-opt08-strips',
    'openstacks-opt11-strips', 'openstacks-opt14-strips',
    'openstacks-strips', 'organic-synthesis-opt18-strips',
    'organic-synthesis-split-opt18-strips', 'parcprinter-08-strips',
    'parcprinter-opt11-strips', 'parking-opt11-strips',
    'parking-opt14-strips', 'pathways', 'pegsol-08-strips',
    'pegsol-opt11-strips', 'petri-net-alignment-opt18-strips',
    'pipesworld-notankage', 'pipesworld-tankage', 'psr-small', 'rovers',
    'satellite', 'scanalyzer-08-strips', 'scanalyzer-opt11-strips',
    'snake-opt18-strips', 'sokoban-opt08-strips',
    'sokoban-opt11-strips', 'spider-opt18-strips', 'storage',
    'termes-opt18-strips', 'tetris-opt14-strips',
    'tidybot-opt11-strips', 'tidybot-opt14-strips', 'tpp',
    'transport-opt08-strips', 'transport-opt11-strips',
    'transport-opt14-strips', 'trucks-strips', 'visitall-opt11-strips',
    'visitall-opt14-strips', 'woodworking-opt08-strips',
    'woodworking-opt11-strips', 'zenotravel'
]

SUITE_SATISFICING = [
    'agricola-sat18-strips', 'airport', 'assembly',
    'barman-sat11-strips', 'barman-sat14-strips', 'blocks',
    'caldera-sat18-adl', 'caldera-split-sat18-adl', 'cavediving-14-adl',
    'childsnack-sat14-strips', 'citycar-sat14-adl',
    'data-network-sat18-strips', 'depot', 'driverlog',
    'elevators-sat08-strips', 'elevators-sat11-strips',
    'flashfill-sat18-adl', 'floortile-sat11-strips',
    'floortile-sat14-strips', 'freecell', 'ged-sat14-strips', 'grid',
    'gripper', 'hiking-sat14-strips', 'logistics00', 'logistics98',
    'maintenance-sat14-adl', 'miconic', 'miconic-fulladl',
    'miconic-simpleadl', 'movie', 'mprime', 'mystery',
    'nomystery-sat11-strips', 'nurikabe-sat18-adl', 'openstacks',
    'openstacks-sat08-adl', 'openstacks-sat08-strips',
    'openstacks-sat11-strips', 'openstacks-sat14-strips',
    'openstacks-strips', 'optical-telegraphs',
    'organic-synthesis-sat18-strips',
    'organic-synthesis-split-sat18-strips', 'parcprinter-08-strips',
    'parcprinter-sat11-strips', 'parking-sat11-strips',
    'parking-sat14-strips', 'pathways',
    'pegsol-08-strips', 'pegsol-sat11-strips', 'philosophers',
    'pipesworld-notankage', 'pipesworld-tankage', 'psr-large',
    'psr-middle', 'psr-small', 'rovers', 'satellite',
    'scanalyzer-08-strips', 'scanalyzer-sat11-strips', 'schedule',
    'settlers-sat18-adl', 'snake-sat18-strips', 'sokoban-sat08-strips',
    'sokoban-sat11-strips', 'spider-sat18-strips', 'storage',
    'termes-sat18-strips', 'tetris-sat14-strips',
    'thoughtful-sat14-strips', 'tidybot-sat11-strips', 'tpp',
    'transport-sat08-strips', 'transport-sat11-strips',
    'transport-sat14-strips', 'trucks', 'trucks-strips',
    'visitall-sat11-strips', 'visitall-sat14-strips',
    'woodworking-sat08-strips', 'woodworking-sat11-strips',
    'zenotravel'
]


def get_project_and_experiment_names():
    script = tools.get_script_path()
    expname, _ = os.path.splitext(os.path.basename(script))
    project_dir = os.path.dirname(script)
    project = os.path.basename(project_dir)
    return project, expname


def get_rel_experiment_dir():
    repo_name = os.path.basename(get_repo_base())
    project, expname = get_project_and_experiment_names()
    return os.path.join(repo_name, project, "data", expname)


def get_repo_base():
    """Get base directory of the repository, as an absolute path.

    Search upwards in the directory tree from the main script until a
    directory with a subdirectory named ".hg" is found.

    Abort if the repo base cannot be found."""
    path = os.path.abspath(tools.get_script_path())
    while os.path.dirname(path) != path:
        if any(os.path.exists(os.path.join(path, x)) for x in [".git", ".hg"]):
            return path
        path = os.path.dirname(path)
    sys.exit("repo base could not be found")


def get_singularity_planner(name):
    planner = Path(os.environ["SINGULARITY_IMAGES"]) / name
    if not planner.is_file():
        logging.critical(f"planner not found: {planner}")
    return planner


def add_evaluations_per_time(run):
    evaluations = run.get('evaluations')
    time = run.get('search_time')
    if evaluations is not None and evaluations >= 100 and time:
        assert isinstance(time, float)
        run['evaluations_per_time'] = evaluations / time
    return run


def get_filters_for_renaming_and_ordering_algorithms(renamings):
    """
    Example::

        renamings = [
            ('downward-seq-sat-fdss-1.py', 'FDSS-1'),
            ('downward-seq-sat-fdss-2.py', 'FDSS-2'),
            ('lmcut', None)  # Don't rename.
        ]
        renaming_filter, order = \
            get_filters_for_renaming_and_ordering_algorithms(renamings)
        exp.add_report(AbsoluteReport(
            filter=[renaming_filter],
            filter_algorithm=order))
    """
    algos = []
    mapping = {}
    for before, after in renamings:
        after = after or before
        algos.append(after)
        mapping[before] = after

    def renaming_filter(run):
        algo = run["algorithm"]
        if algo not in mapping:
            return False
        run["algorithm"] = mapping[algo]
        return run

    return renaming_filter, algos


def escape(s):
    return "''{}''".format(s)


def remove_file(filename):
    try:
        os.remove(filename)
    except OSError:
        pass


def add_scp_steps(exp):
    if not REMOTE:
        exp.add_step(
            'remove-eval-dir', shutil.rmtree, exp.eval_dir,
            ignore_errors=True)

        remote_exp = os.path.join(
            REMOTE_USER.repos, get_rel_experiment_dir())
        exp.add_step('scp-eval-dir', subprocess.call, [
            'scp',
            '-Cr',  # Compress files.
            '%s:%s-eval' % (USER.scp_login, remote_exp),
            '%s-eval' % exp.path])


def fetch_algorithm(exp, expname, algo, new_algo=None):
    """
    Fetch and rename a single algorithm.
    """
    assert not expname.rstrip("/").endswith("-eval")
    new_algo = new_algo or algo

    def algo_filter(run):
        if run["algorithm"] == algo:
            run["algorithm"] = new_algo
            run["id"][0] = new_algo
            return run
        return False

    exp.add_fetcher(
        os.path.join("data", expname + "-eval"),
        filter=algo_filter,
        name="fetch-{new_algo}-from-{expname}".format(**locals()),
        merge=True)

def fetch_algorithms(exp, expname, algos=None, name=None):
    """
    Fetch multiple or all algorithms.
    """
    assert not expname.rstrip("/").endswith("-eval")
    algos = set(algos or [])

    def algo_filter(run):
        return run["algorithm"] in algos

    exp.add_fetcher(
        os.path.join("data", expname + "-eval"),
        filter=algo_filter if algos else None,
        name=name or "fetch-from-{expname}".format(**locals()),
        merge=True)


def get_combination_experiment():
    exp = Experiment()
    exp.add_step(
        "remove-combined-properties",
        remove_file,
        Path(exp.eval_dir) / "properties")
    return exp


# Create custom report class with suitable info and error attributes.
class SmacReport(AbsoluteReport):
    INFO_ATTRIBUTES = ["planner_time_limit", "planner_memory_limit", "command"]
    ERROR_ATTRIBUTES = [
        "domain", "problem", "algorithm", "unexplained_errors", "error",
        "node", "wallclock_time"]


def get_smac_experiment(domains_and_planners, runs_per_domain, attributes, extra_options=None):
    extra_options = extra_options or []
    if REMOTE:
        environment = BaselSlurmEnvironment(
            email=USER.email,
            partition="infai_1",
            memory_per_cpu="6354M")
    else:
        environment = LocalEnvironment(processes=2)

    exp = Experiment(environment=environment)
    exp.add_parser("smac-parser.py")

    result = parse.parse("{base}-{planner_time_limit:d}h-{overall_time_limit:d}h", exp.name)
    safety_time_limit = 23 * 60 * 60
    overall_time_limit = result["overall_time_limit"] * 60 * 60
    overall_memory_limit = 6 * 1024
    planner_time_limit = result["planner_time_limit"] * 60 * 60 if REMOTE else 5
    planner_memory_limit = 5 * 1024
    generators_dir = os.environ["PDDL_GENERATORS"]

    for domain, planner in domains_and_planners:
        planner = get_singularity_planner(planner)
        for seed in range(runs_per_domain):
            run = exp.add_run()
            cmd = [sys.executable, str(DIR.parent / "src" / "generate-instances.py"),
                "--overall-time-limit", str(overall_time_limit),
                "--planner-time-limit", str(planner_time_limit),
                "--planner-memory-limit", str(planner_memory_limit),
                "--random-seed", str(seed),
                "--generators-dir", generators_dir,
                "--smac-output-dir", str(Path(exp.path) / f"smac-output-{domain}"),
                domain, planner] + extra_options
            run.add_command(
                "generate",
                cmd,
                time_limit=safety_time_limit,
                memory_limit=overall_memory_limit,
                hard_stdout_limit=50 * 1024)
            domain_setting = f"{domain}"
            problem = f"seed-{seed}"
            algorithm = f"smac"
            run.set_property("planner_time_limit", planner_time_limit)
            run.set_property("planner_memory_limit", planner_memory_limit)
            run.set_property("domain", domain_setting)
            run.set_property("problem", problem)
            run.set_property("algorithm", algorithm)
            run.set_property("command", cmd)
            # Every run has to have a unique id in the form of a list.
            run.set_property("id", [domain_setting, problem, algorithm])

    exp.add_step("build", exp.build)
    exp.add_step("start", exp.start_runs)
    exp.add_fetcher(name="fetch")

    add_scp_steps(exp)

    report = Path(exp.eval_dir) / f"{exp.name}.html"
    exp.add_report(
        SmacReport(attributes=attributes),
        outfile=report)
    exp.add_step("open-report", subprocess.call, ["xdg-open", report])
    exp.add_step("publish-report", subprocess.call, ["publish", report])

    taskwise_report = Path(exp.eval_dir) / f"{exp.name}-taskwise.html"
    exp.add_report(
        TaskwiseReport(attributes=attributes),
        outfile=taskwise_report)
    exp.add_step("publish-taskwise-report", subprocess.call, ["publish", taskwise_report])

    return exp
