#
# Process pool. Similar to multiprocess.Pool, but with no limits
#
# Author: BOFH <bo@suse.de>
#


class Singleton(type):
    _instances = dict()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._instances[cls]


class Pool(object):
    """
    Pool object.
    """
    __metaclass__ = Singleton

    def __init__(self):
        self.__processes = list()

    def run(self, process, join=False):
        """
        Run a process
        """
        process.daemon = not join
        process.start()
        if process.daemon:
            self.__processes.append(process)
        else:
            process.join()

    def join(self):
        """
        Wait for the active processes.
        :return:
        """
        while self.__processes:
            buff = list()
            for process in self.__processes:
                if process.is_alive():
                    buff.append(process)
            self.__processes = buff[:]
