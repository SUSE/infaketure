# Fake action of up2date
# SUMA tells what to scan on the client machine, this will return a fake data back.
#
# Author: BOFH <bo@suse.de>


class Action(object):
    def __init__(self, **returners):
        self.__returners__ = returners
        self.__target__ = None

    def __getattr__(self, item):
        self.__target__ = item
        return self

    def __call__(self, *args, **kwargs):
        obj = self.__returners__.get(self.__target__)
        return callable(obj) and obj(*args, **kwargs) or obj or (0, "OK",)


class Dispatcher(object):
    def __init__(self, path=None):
        """
        Action dispatcher.
        """
        self.__traverse_path__ = []
        for element in (path or "").split("."):
            getattr(self, element)

    def __getattr__(self, item):
        self.__traverse_path__.append(item)
        return self

    def _no_ops(self, *args, **kwargs):
        return 0, "no-ops for caching", {}

    def __get_action(self):
        action = Action()
        action.packages = Action(checkNeedUpdate=(0, "rpm database not modified since last update "
                                                     "(or package list recently updated)", {}),
                                 setLocks=(0, "Wrote /etc/zypp/locks", {}),
                                 remove=self._no_ops,
                                 update=self._no_ops,
                                 patch_install=self._no_ops,
                                 runTransaction=self._no_ops,
                                 fullUpdate=self._no_ops,
                                 refresh_list=(0, "rpmlist refreshed", {}),
                                 touch_time_stamp=(0, "unable to open the timestamp file", {}),
                                 verify=self._no_ops,
                                 verifyAll=self._no_ops,)
        action.reboot = Action()
        action.rhnsd = Action()
        action.script = Action()
        action.scap = Action()
        action.systemid = Action()
        action.errata = Action()
        action.distupgrade = Action()
        action.configfiles = Action()
        action.hoo = Action(foobar=lambda *a, **k: (2, "Foo",))

        return action

    def __call__(self, *args, **kwargs):
        action = self.__get_action()
        for p_elm in self.__traverse_path__:
            action = getattr(action, p_elm)
        return action(*args, **kwargs)


if __name__ == '__main__':
    print Dispatcher().test.test.test.woo.hoo.foobar("are", you="puzzled?")  # Returns (2, 'Foo')
