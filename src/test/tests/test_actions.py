__author__ = 'bo'

import unittest
import sys
from infaketure.actions import Dispatcher
from infaketure.actions import Action


class TestActions(unittest.TestCase):
    def setUp(self):
        self.dispatcher = Dispatcher(None, None)

    def tearDown(self):
        pass

    def test_dispatcher(self):
        self.assertEqual(True, False)
