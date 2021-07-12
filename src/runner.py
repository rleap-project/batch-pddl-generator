import resource
import subprocess


class Runner:
    def __init__(self, domain, command, time_limit, memory_limit, generators_dir):
        self.domain = domain
        self.command = command
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.generators_dir = generators_dir

    def run_planner(self, plan_dir):
        """Run the planner in the given directory on the prepared task."""

        def set_limit(limit_type, soft, hard=None):
            if hard is None:
                hard = soft
            resource.setrlimit(limit_type, (soft, hard))

        def prepare_call():
            set_limit(resource.RLIMIT_CPU, self.time_limit, hard=self.time_limit + 1)
            set_limit(resource.RLIMIT_AS, self.memory_limit * 1024 ** 2)  # bytes
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
