#
# Get the metadata of examined machine
#

__author__ = 'bo'

import subprocess
import getpass
import os
from infaketure.sshcall import SSHCall


class LocalCaller(object):
    """
    Local caller.
    """

    def call(self, cmd, ignore_failure=False):
        """
        Call a command on the remote host.
        """
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = proc.communicate()
        status = proc.poll()

        return (out or err or '').strip(), ignore_failure is False and status or 0


class HardwareInfo(object):
    """
    Get hardware info of the target machine.
    """
    pass


class SoftwareInfo(object):
    def __init__(self, host, user=None):
        if host is None or host.lower().strip() == 'localhost':
            self._caller = LocalCaller()
        else:
            self._caller = SSHCall(user or getpass.getuser(), host)

    def get_pkg_info(self, *packages):
        """
        Get the information about given packages.

        :param packages:
        :return:
        """
        installed = dict()
        for pkg_info in self._caller.call("/bin/rpm -qa --queryformat='%{NAME}\t%{VERSION}\t%{RELEASE}\t%{VENDOR}\n'",
                                          ignore_failure=True)[0].split(os.linesep):
            name, version, release, vendor = pkg_info.split("\t")
            installed[name] = {"version": version, "release": release, "vendor": vendor}

        data = dict()
        for pkg_name in packages:
            if pkg_name in installed:
                data[pkg_name] = installed.get(pkg_name)

        return data
