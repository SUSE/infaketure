import sys


INFO = 0
WARNING = 1
ERROR = 2


def _info(msg, **kwargs):
    print >> sys.stdout, "INFO:", msg


def _warning(msg, **kwargs):
    print >> sys.stderr, "WARNING:", msg


def _error(msg, **kwargs):
    print >> sys.stderr, "ERROR: {0}!".format(msg)
    if "panic" in kwargs:
        sys.exit(1)


_msg = {
    INFO: _info,
    WARNING: _warning,
    ERROR: _error,
}


def cli_msg(level, msg, **kwargs):
    """
    Print CLI message.

    :param level:
    :param msg:
    :return:
    """

    _msg[ERROR if level not in [INFO, WARNING, ERROR] else level](msg, **kwargs)
