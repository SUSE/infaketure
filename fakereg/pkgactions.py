#
# Package actions
# Author: bo@suse.de
#

import check

class PackageActions(object):
    """
    Package actions responder.
    """
    def __init__(self, caller, sid):
        self.caller = caller
        self.sid = sid

    def update(self, *packages, **kwargs):
        """
        Install/update fake packages.

        :param args:
        :param kwargs:
        :return:
        """
        if not packages:
            return 1, "No packages has been requested", {}

        profile = self.caller.db.get_host_profiles(host_id=self.sid)
        packages = packages[0]
        for n_pkg_meta in packages:
            n, v, r, e, a = n_pkg_meta
            package = dict()
            package["name"] = n
            package["epoch"] = e
            package["version"] = v
            package["release"] = r
            package["arch"] = a

            # Existing package update
            prf_pkgs = list()
            for p_pkg in profile.packages:
                if p_pkg.get('name') != n:
                    prf_pkgs.append(p_pkg)

            prf_pkgs.append(package)
            profile.packages = prf_pkgs[:]
            del prf_pkgs

        self.caller.db.update_profile(profile)
        self.caller.db.connection.commit()
        check.FakeRHNServer(self.caller.get_server()).registration.update_packages(profile.src, profile.packages)

        return 0, "{0} Fake package{1} has been updated".format(len(packages), len(packages) > 1 and "s" or ""), {}

    def remove(self, *args, **kwargs):
        """
        Remove fake packages.

        :param args:
        :param kwargs:
        :return:
        """
