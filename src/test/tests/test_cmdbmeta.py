#
# Tetst CMDB meta
#

__author__ = 'bo'

import unittest
import uuid
from infaketure.cmdbmeta import SoftwareInfo


class TestCMDBMeta(unittest.TestCase):
    """
    Test CMDB metadata.
    """

    def test_package_info(self):
        """
        Test package information
        :return:
        """
        dummy = str(uuid.uuid4())
        pkgs = SoftwareInfo('localhost').get_pkg_info('aaa_base', 'coreutils', dummy)
        self.assertTrue(dummy not in pkgs)
        self.assertTrue('aaa_base' in pkgs)
        self.assertTrue('coreutils' in pkgs)

        pkg = pkgs.get('coreutils')

        self.assertTrue(pkg)
        self.assertTrue(pkg.get('version'))
        self.assertTrue(pkg.get('release'))
        self.assertTrue(pkg.get('vendor'))
