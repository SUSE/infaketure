#!/usr/bin/python
#
"""
Main unittest runner.
"""
__author__ = 'bo'

import unittest
import tempfile
import random
import string
import os
import sys
import shutil

sys.path.append("../")

from infaketure import store


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

    def tearDown(self):
        """
        Teardown the test case.

        :return: void
        """
        shutil.rmtree(self._db_location)

    def test_init(self):
        """
        Test DB file structure initialization.

        :return: void
        """
        self.db.open()
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'hardware', 'hosts'])

    def test_close(self):
        """
        Test DB close.

        :return: void
        """
        self.db.open()
        self.assertTrue(self.db.is_closed())
        self.db.close()
        self.assertFalse(self.db.is_closed())

    def test_flush(self):
        """
        Test flushing (deleting) one table.

        :return: void
        """
        self.db.open()
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
        self.db.open()
        self.db.cursor.execute("CREATE TABLE dummy (id INTEGER, TEST CHAR(255))")
        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'dummy', 'hardware', 'hosts'])

        self.db.purge()

        self.db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        self.assertEqual(sorted([tbl_name[0] for tbl_name in self.db.cursor.fetchall()]),
                         ['configs', 'credentials', 'hardware', 'hosts'])
        self.db.close()


if __name__ == '__main__':
    unittest.main()
