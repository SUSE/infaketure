#
# Load processor.
# Schedules tasks from SUMA and executes on clients.
#
# Author: bo@suse.de
#

import os
import time
import random


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

    def load_scenario(self, scenario):
        """
        Load scenario and its config.
        """
        if not os.path.exists(scenario):
            raise Exception("Path '{0}' is not accessible.".format(scenario))

        self._scenario = list()
        for line in open(scenario):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:  # Config element has key=value syntax
                k, v = [elm.strip() for elm in line.strip().split("=", 1)]
                if "," in v:
                    v = [elm.strip() for elm in v.split(",")]
                self.config[k] = v
                continue

            # Command action does not have key=value syntax
            line = [elm for elm in line.replace("\t", " ").split(" ") if elm]
            call_meta = {'method': line.pop(0), 'args': list(), 'kwargs': dict()}
            for param in line:
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
        if cycle:
            for iteration in xrange(0, cycle):
                self.__call()
                if callback is not None:
                    callback(*cb_args, **cb_kwargs)
        else:
            while True:
                self.__call()
                if callback is not None:
                    callback(*cb_args, **cb_kwargs)

    def __call(self):
        """
        One tick call.
        """
        for call_params in self._scenario:
            try:
                getattr(self._load_processor, call_params["method"])(*call_params["args"], **call_params["kwargs"])
            except Exception as ex:
                print ex

        time.sleep(int(self.config.get("loop.sleep", 10)))


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
            packages = self.api.system.get_available_packages(int(profile.sid))
            to_install = list()
            for itr in range(0, int(options.get("pkg", 1))):
                to_install.append(packages[random.randint(0, len(packages) - 1)]["id"])
            self.api.system.install_package(int(profile.sid), *to_install)

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
