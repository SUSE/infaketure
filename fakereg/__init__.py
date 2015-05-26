import sys


INFO = 0
WARNING = 1
ERROR = 2


def _info(msg):
    print >> sys.stdout, "INFO:", msg


def _warning(msg):
    print >> sys.stderr, "WARNING:", msg


def _error(msg):
    print >> sys.stderr, "ERROR: {0}!".format(msg)


_msg = {
    INFO: _info,
    WARNING: _warning,
    ERROR: _error,
}


def cli_msg(level, msg):
    """
    Print CLI message.

    :param level:
    :param msg:
    :return:
    """

    _msg[ERROR if level not in [INFO, WARNING, ERROR] else level](msg)
