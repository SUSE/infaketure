"""
SQLite tests
"""
__author__ = 'bo'

import unittest
import tempfile
import random
import string
import os
import shutil

from infaketure import store
from infaketure.store import CMDBBaseProfile


class TestSQLiteHandler(unittest.TestCase):
    def setUp(self):
        """
        Setup the test case.

        :return: void
        """
        rnd = random.Random()
        self._db_location = tempfile.mkdtemp()
        self._db_file = os.path.join(self._db_location,
                                     ''.join(map(lambda elm: rnd.choice(string.ascii_letters), range(10))))
        self.db = store.DBOperations(self._db_file)
        self.db.open()

    def tearDown(self):
        """
        Teardown the test case.

        :return: void
        """
        self.db.close()
        shutil.rmtree(self._db_location)

    def test_init(self):
        """
        Test DB file structure initialization.

        :return: void
        """
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'hardware', 'hosts'])

    def test_close(self):
        """
        Test DB close.

        :return: void
        """
        self.assertTrue(self.db.is_closed())
        self.db.close()
        self.assertFalse(self.db.is_closed())

    def test_flush(self):
        """
        Test flushing (deleting) one table.

        :return: void
        """
        self.db.cursor.execute("SELECT HID FROM CREDENTIALS")
        self.assertEqual(0, len(self.db.cursor.fetchall()))

        self.db.cursor.execute("INSERT INTO CREDENTIALS (HID, S_BODY) VALUES (?, ?)", (0, "DUMMY"))

        self.db.cursor.execute("SELECT HID FROM CREDENTIALS")
        self.assertEqual(1, len(self.db.cursor.fetchall()))

        self.db.flush("credentials")

        self.db.cursor.execute("SELECT HID FROM CREDENTIALS")
        self.assertEqual(0, len(self.db.cursor.fetchall()))

    def test_purge(self):
        """
        Purge the entire database and thus re-init it.

        :return: void
        """
        self.db.cursor.execute("CREATE TABLE dummy (id INTEGER, TEST CHAR(255))")
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'dummy', 'hardware', 'hosts'])

        self.db.purge()

        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'hardware', 'hosts'])

    def test_next_id(self):
        """
        Get next ID from the DB.

        :return:
        """
        next_id = self.db.get_next_id("hosts")
        self.assertEqual(next_id, 1)
        self.db.cursor.execute("INSERT INTO hosts (ID, SID, HOSTNAME, SID_XML) VALUES (?, ?, ?, ?)",
                               (next_id, "-", "-", "-",))

        next_id = self.db.get_next_id("hosts")
        self.assertEqual(next_id, 2)
        self.db.cursor.execute("INSERT INTO hosts (ID, SID, HOSTNAME, SID_XML) VALUES (?, ?, ?, ?)",
                               (next_id, "-", "-", "-",))

        next_id = self.db.get_next_id("hosts")
        self.assertEqual(next_id, 3)
        self.db.cursor.execute("INSERT INTO hosts (ID, SID, HOSTNAME, SID_XML) VALUES (?, ?, ?, ?)",
                               (next_id, "-", "-", "-",))

    def test_profile_create(self):
        """
        Test profile create

        :return:
        """
        # Fake profile
        profile = type('profile', (), {})
        profile.sid = "10001000"
        profile.src = "src"
        profile.name = "name"
        profile.hardware = "hardware"
        profile.login_info = {'login': 'info'}
        profile.packages = list()

        # Fake rhnreg module
        rhnreg = type('rhnreg', (), {})
        rhnreg.cfg = {'cfg': 'test'}
        store.rhnreg = rhnreg

        self.db.create_profile(profile)
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['SYS10001000PKG', 'configs', 'credentials', 'hardware', 'hosts'])

        profiles = self.db.get_host_profiles()
        self.assertEqual(len(profiles), 1)
        self.assertTrue(isinstance(profiles[0], CMDBBaseProfile))

        cmdb_profile = profiles[0]
        self.assertEqual(cmdb_profile.sid, profile.sid)
        self.assertEqual(cmdb_profile.src, profile.src)
        self.assertEqual(cmdb_profile.name, profile.name)
        self.assertEqual(cmdb_profile.hardware, profile.hardware)
        self.assertEqual(cmdb_profile.login_info, profile.login_info)
        self.assertEqual(cmdb_profile.packages, profile.packages)
