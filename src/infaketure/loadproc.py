#
# Load processor.
# Schedules tasks from SUMA and executes on clients.
#
# Author: bo@suse.de
#

import time
import random
import multiprocessing
import procpool
import ConfigParser


class ScenarioPreprocessor(object):
    """
    To make life easier, but still using default Python config parser.
    This fixes on the fly 'wrong syntax' of the INI file, that Python
    does not likes.
    """
    def __init__(self, scenario):
        self.idx = 0
        self.__body = list()
        for line in open(scenario):
            line = line.strip()
            if not line or line.startswith("#"):  # Comments, empty lines
                continue
            elif "=" in line and not line.split("=", 1)[1]:  # No value lines
                line += " void"

            self.__body.append(line)

    def readline(self):
        """
        Read one line.
        """

        if (self.idx + 1) <= len(self.__body):
            line = self.__body[self.idx]
            self.idx += 1
        else:
            line = None

        return line


class LoadScenarioCaller(object):
    """
    Load scenario caller.
    This reads the scenario and calls load processor accordingly.
    """

    def __init__(self, load_processor):
        """
        Constructor for the load scenario caller
        """
        self._load_processor = load_processor
        self._scenario = None
        self.config = {"loop.cycle": 0, "loop.sleep": 10}
        self.verbose = False

    def load_scenario(self, scenario):
        cfg_parser = ConfigParser.ConfigParser()
        cfg_parser.readfp(ScenarioPreprocessor(scenario))
        self._scenario = list()

        self.config["loop.cycle"] = cfg_parser.get("loop", "cycle", self.config["loop.cycle"])
        self.config["loop.sleep"] = cfg_parser.get("loop", "sleep", self.config["loop.sleep"])

        # Get PCP metrics
        for metric_name in cfg_parser.options("pcp metrics"):
            metric_args = cfg_parser.get("pcp metrics", metric_name)
            if metric_args == 'void':
                metric_args = ""
            self.config["pcp.metric.{0}".format(metric_name)] = metric_args

        # Get PCP settings
        for pcp_setting in cfg_parser.options("pcp"):
            pcp_setting_args = cfg_parser.get("pcp", pcp_setting)
            self.config["pcp.{0}".format(pcp_setting)] = pcp_setting_args

        # Get actions
        for action in cfg_parser.options("actions"):
            call_meta = {'method': action, 'args': list(), 'kwargs': dict()}

            action_params = [elm for elm in cfg_parser.get("actions", action).replace("\t", " ").split(" ") if elm]
            for param in action_params:
                param = param.split(":")
                if len(param) == 1:
                    call_meta['args'].append(param[0])
                elif len(param) == 2:
                    if param[1].lower() == "true":
                        param[1] = True
                    elif param[1].lower() == "false":
                        param[1] = False
                    call_meta['kwargs'][param[0]] = param[1]
            self._scenario.append(call_meta)

    def run(self, callback=None, *cb_args, **cb_kwargs):
        """
        Run the scenario.
        """
        cycle = int(self.config.get("loop.cycle", 0))
        pause = int(self.config.get("loop.sleep", 0))

        iteration = 0
        while True:
            if cycle and iteration == cycle:
                break
            self.__call()
            if callback is not None:
                callback(*cb_args, **cb_kwargs)
            if self.verbose:
                print "--- Iteration finished ---"
                print "Sleeping", pause, "seconds"
            time.sleep(pause)
            if cycle:
                iteration += 1

    def __call(self):
        """
        Call scenario params
        """
        for call_params in self._scenario:
            try:
                getattr(self._load_processor, call_params["method"])(*call_params["args"], **call_params["kwargs"])
            except Exception as ex:
                print ex
        time.sleep(int(self.config.get("loop.sleep", 10)))
        self._load_processor.pool.join()


class LoadScheduleProcessor(object):
    """
    Load processor that acts like an administrator by
    scheduling particular tasks on SUMA and executing them on clients.
    """

    def __init__(self, db, api):
        """
        Constructor.
        :return:
        """
        self.db = db
        self.api = api
        self.pool = procpool.Pool()

    def check_in(self, *sids):
        """
        Check-in machines, specified by system IDs or all known, if not specified.

        :param sids:
        :return:
        """

    def downgrade(self, *sids):
        """
        Downgrade machines by sids or all, if none.

        :param sids: List of session IDs
        :return:
        """

    def upgrade(self):
        """
        Upgrade all upgradeable machines.

        :return:
        """

    def install(self, *sids, **options):
        """
        Install a set of random packages specified by amount on the particular machines (or all, if not specified).
        Set download: param to True in order to let installed packages actually be downloaded from SUMA.
        Set io: parameter to False, so the package will be processed immediately, otherwise with some sleep time.

        Options:
            pkg
              Amount of packages to install

            download
              True or False

            io
              True or False.

        :param sids:
        :param options: Additional options for the install
        :return:
        """
        for profile in self.db.get_host_profiles():
            self.pool.run(multiprocessing.Process(target=self.__install_one, args=(profile,), kwargs=options))

    def __install_one(self, profile, **options):
        amount = int(options.get("pkg", 1))
        print "Installing {0} packages on {1}".format(amount, profile.sid)
        packages = self.api.system.get_available_packages(int(profile.sid))
        to_install = list()
        for itr in range(0, amount):
            to_install.append(packages[random.randint(0, len(packages) - 1)]["id"])
        self.api.system.install_package(int(profile.sid), *to_install)
        print "Package installation finished {0}".format(profile.sid)

    def remove(self, *sids, **options):
        """
        Remove a set of random packages specified by amount on the particular machines (or all, if not specified).

        :param amount:
        :param sids:
        :return:
        """

    def register(self, amount):
        """
        Register an amount of clients.

        :param amount:
        :return:
        """

    def unregister(self, *sids):
        """
        Unregister machines from the SUMA by specified system IDs or all, if none.

        :param sids:
        :return:
        """
