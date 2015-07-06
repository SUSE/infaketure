#
# Tetst CMDB meta
#

__author__ = 'bo'

import unittest
import uuid
import os
import random
from infaketure.cmdbmeta import SoftwareInfo


class TestCMDBMeta(unittest.TestCase):
    """
    Test CMDB metadata.
    """

    def setUp(self):
        self.fake_packages = "php5-ctype\t5.3.3\t0.19.1\topenSUSE\n" \
                             "ant-apache-oro\t1.7.1\t12.2\topenSUSE\n" \
                             "libxmi0\t2.6\t3.1\topenSUSE\n" \
                             "xml-commons-resolver\t1.1\t267.30\topenSUSE\n" \
                             "unixODBC\t2.2.12\t204.3.1\topenSUSE\n" \
                             "libcrystalhd3\t3.6.5\t6.1\thttp://packman.links2linux.de\n" \
                             "libelf-devel\t0.147\t1.19\topenSUSE\n" \
                             "kernel-syms\t2.6.34.10\t0.6.1\topenSUSE\n"
        self.packages = self.fake_packages.strip()
        self.test_pkgs = list()
        for pkg_data in self.packages.split(os.linesep):
            self.test_pkgs.append(pkg_data.split("\t"))
        self.softinfo = SoftwareInfo('localhost')
        self.softinfo._caller.call = lambda cmd: (self.fake_packages, 0,)

    def test_package_info_presense(self):
        """
        Test package information
        :return:
        """
        dummy = str(uuid.uuid4())
        pkg = self.test_pkgs[0][0]
        pkgs = self.softinfo.get_pkg_info(pkg, dummy)
        self.assertTrue(dummy not in pkgs)
        self.assertTrue(pkg in pkgs)

        pkg = pkgs.get(pkg)

        self.assertTrue(pkg)
        self.assertTrue(pkg.get('version'))
        self.assertTrue(pkg.get('release'))
        self.assertTrue(pkg.get('vendor'))

    def test_package_info_correctness(self):
        """
        Get ten random packages from the current system, get their info and verify.
        :return:
        """

        descr_pkgs = self.softinfo.get_pkg_info(*[name[0] for name in self.test_pkgs])

        for name, version, release, vendor in self.test_pkgs:
            self.assertTrue(name in descr_pkgs)
            self.assertEqual(version, descr_pkgs.get(name).get('version'))
            self.assertEqual(release, descr_pkgs.get(name).get('release'))
            self.assertEqual(vendor, descr_pkgs.get(name).get('vendor'))

    def test_package_info_wildcards(self):
        """
        Test for package matching with the wildcards

        :return:
        """
        descr_pkgs = self.softinfo.get_pkg_info('kernel*', '*ODBC', '*apache*', 'libxmi0')
        for pkg_name in ['ant-apache-oro', 'unixODBC', 'libxmi0', 'kernel-syms']:
            self.assertTrue(pkg_name in descr_pkgs)
