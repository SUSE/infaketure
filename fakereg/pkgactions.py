#
# Package actions
# Author: bo@suse.de
#


class PackageActions(object):
    """
    Package actions responder.
    """
    def __init__(self, db, sid):
        self.db = db
        self.sid = sid

    def update(self, *packages, **kwargs):
        """
        Install/update fake packages.

        :param args:
        :param kwargs:
        :return:
        """
        profile = self.db.get_host_profiles(host_id=self.sid)
        for pkg in packages:
            n, v, r, e, a = pkg[0]
            print "Update called over SID", self.sid
            prf_pkgs = list()
            update_pkg = dict()
            for package in profile.packages:
                if package.get('name') == n:
                    update_pkg = package.copy()
                else:
                    prf_pkgs.append(package)
            profile.packages = prf_pkgs[:]
            del prf_pkgs

            update_pkg["name"] = n
            update_pkg["epoch"] = e
            update_pkg["version"] = v
            update_pkg["release"] = r
            update_pkg["arch"] = a

            profile.packages.append(update_pkg)
            self.db.update_profile(profile)
        self.db.connection.commit()

        return 0, "{0} Fake package{1} has been updated".format(len(packages), len(packages) > 1 and "s" or ""), {}

    def remove(self, *args, **kwargs):
        """
        Remove fake packages.

        :param args:
        :param kwargs:
        :return:
        """
