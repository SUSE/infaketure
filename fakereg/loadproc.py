#
# Load processor.
# Schedules tasks from SUMA and executes on clients.
#
# Author: bo@suse.de
#


class LoadProcessor(object):
    """
    Load processor that acts like an administrator by
    scheduling particular tasks on SUMA and executing them on clients.
    """

    def __init__(self):
        """
        Constructor.
        :return:
        """

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

    def install(self, amount, download=False, io=True, *sids):
        """
        Install a set of random packages specified by amount on the particular machines (or all, if not specified).
        Set download: param to True in order to let installed packages actually be downloaded from SUMA.
        Set io: parameter to False, so the package will be processed immediately, otherwise with some sleep time.

        :param amount:
        :param download:
        :param io:
        :param sids:
        :return:
        """

    def remove(self, amount, *sids):
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

