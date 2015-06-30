#
# SSH tools
#

import subprocess

__author__ = 'bo'


class SSHCall(object):
    """
    Dead-simple SSH wrapper.
    """
    SSH_CMD = 'ssh -oStrictHostKeyChecking=no -oBatchMode=yes {user}@{host} "{command}"'
    SCP_TO_CMD = 'scp {src_path} {user}@{host}:{dest_path}'
    SCP_FROM_CMD = 'scp {user}@{host}:{src_path} {dest_path}'

    def __init__(self, user, host):
        self._host = host
        self._user = user

    def __call(self, tpl, **kwargs):
        """
        Call SSH to copy or other commands.
        """
        proc = subprocess.Popen(tpl.format(**kwargs), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out, err = proc.communicate()
        status = proc.poll()

        # Many commands messes up the STDOUT with the STDERR.
        # To detect which belongs to where, we use status code.
        # If it is non-zero, then this is an error message,
        # regardless where it appears: in STDOUT or STDERR.
        return (out or err or '').strip(), kwargs.get("ignore_failure") is False and status or 0

    def call(self, cmd, ignore_failure=False):
        """
        Call a command on the remote host.
        """
        return self.__call(self.SSH_CMD, user=self._user, host=self._host, command=cmd, ignore_failure=ignore_failure)

    def check_keypair(self):
        """
        Check if RSA keypair is deployed and is valid.
        """
        msg, status = self.call("uptime")
        if status:
            raise Exception(msg)

        return msg, status

    def copy_to(self, src_path, dest_path):
        """
        Copy files from the local machine to the remote machine.
        """
        self.__call(self.SCP_TO_CMD, user=self._user, host=self._host, src_path=src_path, dest_path=dest_path)

    def copy_from(self, src_path, dest_path):
        """
        Copy files from the remote machine to the local machine.
        """
        self.__call(self.SCP_FROM_CMD, user=self._user, host=self._host, src_path=src_path, dest_path=dest_path)
