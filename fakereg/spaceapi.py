#
# The part that talks to the "real" Spacewalk API
# Author: BOFH <bo@suse.de>
#

import xmlrpclib
import datetime
import time


class _BaseSpaceAPI(object):
    """
    Base API for Spacewalk.
    """
    def __init__(self, url):
        self.conn = xmlrpclib.ServerProxy(url)
        self.token = None

    def login(self, user, password):
        """
        Login to the Spacewalk.
        """
        _logged = False
        for tryout in range(0, 5):
            try:
                self.token = self.conn.auth.login(user, password)
                _logged = True
            except Exception as ex:
                print "Login error: {0}. Trying {1} time.".format(ex, (tryout + 1))
                time.sleep(5)
            if _logged:
                break

    def logout(self):
        """
        Logout from the Spacewalk.
        """
        self.conn.auth.logout(self.token)


class _SystemsAPI(_BaseSpaceAPI):
    """
    Systems API.
    """
    def get_systems(self):
        """
        Get registered systems.
        """
        ret = list()
        systems = self.conn.system.listSystems(self.token)
        for system in systems:
            data = dict()
            for k, v in system.items():
                if k == 'id':
                    data['sid'] = 'ID-{0}'.format(v)
                data[k] = v
            ret.append(data)

        return ret

    def delete_system_by_sid(self, sid):
        """
        Delete registered system.
        """
        self.conn.system.deleteSystem(self.token, sid)

    def get_available_packages(self, sid):
        """
        Get the list of all available packages.
        """
        return self.conn.system.listLatestInstallablePackages(self.token, sid)

    def install_package(self, sid, *pkg_ids):
        """
        Schedule packages installation.
        """
        self.conn.system.schedulePackageInstall(self.token, sid, pkg_ids, datetime.datetime.now())


class SpaceAPI(_BaseSpaceAPI):
    """
    Container.
    """
    def __init__(self, url):
        _BaseSpaceAPI.__init__(self, url)
        self.__url = url
        self.system = None

    def login(self, user, password):
        super(SpaceAPI, self).login(user, password)
        self.system = _SystemsAPI(self.__url)
        self.system.token = self.token
