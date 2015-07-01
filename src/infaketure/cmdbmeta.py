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


class MachineInfo(object):
    """
    Base class for machine information extraction.
    """
    def __init__(self, host, user=None):
        if host is None or host.lower().strip() == 'localhost':
            self._caller = LocalCaller()
        else:
            self._caller = SSHCall(user or getpass.getuser(), host)


class HardwareInfo(MachineInfo):
    """
    Get hardware info of the target machine.
    """
    def get_disk_drives(self):
        """
        Get disk drives
        """
        devices = list()
        for mounted_device in self._call("cat /etc/mtab").strip().split("\n"):
            if mounted_device.startswith('/dev/'):
                devices.append(self._call("hdparm -i {0}".format(mounted_device.split(" ")[0])))

    def _call(self, cmd):
        nfo, status = self._caller.call(cmd)
        if status:
            raise Exception(nfo)

        return nfo

    def get_memory(self):
        """
        Get general memory info
        """
        return self._call("cat /proc/meminfo")

    def get_cpu(self):
        """
        Get CPU info
        """
        return self._call("cat /proc/cpuinfo")

    def get_disk_space(self):
        """
        Get disk space
        """
        return self._call("df -h")


class SoftwareInfo(MachineInfo):
    """
    Get installed software information
    """
    def get_pkg_info(self, *packages):
        """
        Get the information about given packages.

        :param packages:
        :return:
        """
        installed = dict()
        pkgs_meta, status = self._caller.call(
            "/bin/rpm -qa --queryformat='%{NAME}\t%{VERSION}\t%{RELEASE}\t%{VENDOR}\n'")
        if status:
            raise Exception(pkgs_meta)

        for pkg_info in pkgs_meta.strip().split(os.linesep):
            name, version, release, vendor = pkg_info.split("\t")
            installed[name] = {"version": version, "release": release, "vendor": vendor}

        data = dict()
        for pkg_name in packages:
            for i_pkg_name in installed.keys():
                if (pkg_name.startswith('*') and i_pkg_name.endswith(pkg_name.replace('*', ''))) \
                        or (pkg_name.endswith('*') and i_pkg_name.startswith(pkg_name.replace('*', ''))) \
                        or (pkg_name.startswith('*') and pkg_name.endswith('*') and
                            i_pkg_name.find(pkg_name.replace('*', '')) > 0) \
                        or (pkg_name == i_pkg_name):
                    data[i_pkg_name] = installed.get(i_pkg_name)

        return data
