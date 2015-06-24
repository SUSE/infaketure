__author__ = 'bo'

import unittest
import uuid
from infaketure.actions import Dispatcher
from infaketure.actions import Action


class TestActions(unittest.TestCase):
    def setUp(self):
        """
        Setup the actions test.

        :return:
        """
        self.dispatcher = Dispatcher(None, None)

    def test_action_object(self):
        """
        Test action object.

        :return:
        """
        value = uuid.uuid4().hex
        action = Action()
        action.one.two.three.four.five = value
        self.assertEqual(action.one.two.three.four.five, value)

    def test_dispatcher(self):
        """
        Test dispatcher object.

        :return:
        """
        for action in ['reboot', 'rhnsd', 'script', 'scap', 'systemid',
                       'errata', 'distupgrade', 'configfiles', 'packages']:
            self.assertTrue(hasattr(self.dispatcher, action))
