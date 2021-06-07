import logging
from pathlib import Path
import resource
import shutil
import subprocess

import utils


TMP_PLAN_DIR = "plan"


class Runner:
    def __init__(self, domain, command, time_limit, memory_limit, generators_dir):
        self.domain = domain
        self.command = command
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.generators_dir = generators_dir

    def generate_input_files(self, parameters, seed, output_dir):
        # Write problem file.
        task_name = utils.join_parameters(parameters)
        plan_dir = Path(output_dir) / TMP_PLAN_DIR / task_name / str(seed)
        shutil.rmtree(plan_dir, ignore_errors=True)
        plan_dir.mkdir(parents=True)
        problem_file = plan_dir / "problem.pddl"
        domain_file = plan_dir / "domain.pddl"
        command = self.domain.get_generator_command(self.generators_dir, parameters, seed)
        logging.debug("Generator command: {}".format(" ".join(command)))
        self.domain.generate_problem(command, problem_file, domain_file)

        if not domain_file.is_file():
            shutil.copy2(self.domain.get_domain_file(self.generators_dir), domain_file)
        assert problem_file.is_file()

        return plan_dir

    def run_planner(self, plan_dir):
        """Run the planner in the given directory on the prepared task."""
        def set_limit(limit_type, limit):
            resource.setrlimit(limit_type, (limit, limit))

        def prepare_call():
            set_limit(resource.RLIMIT_CPU, self.time_limit)
            set_limit(resource.RLIMIT_AS, self.memory_limit * 1024**2)  # bytes
            set_limit(resource.RLIMIT_CORE, 0)

        logfilename = plan_dir / "run.log"
        errfilename = plan_dir / "run.err"

        with open(logfilename, "w") as logfile, open(errfilename, "w") as errfile:
            p = subprocess.Popen(
                self.command,
                cwd=plan_dir,
                stdout=logfile,
                stderr=errfile,
                preexec_fn=prepare_call,
            )
            retcode = p.wait()

        # Delete empty logfiles and errfiles.
        for path in [logfilename, errfilename]:
            if path.stat().st_size == 0:
                path.unlink()

        return retcode
