import unittest
import tempfile
import os
from infaketure import loadproc
import ConfigParser


class TestScenarioLoader(unittest.TestCase):
    """
    Test scenario loader.
    """

    def setUp(self):
        scenario_src = """
[loop]
  cycle = 1
  sleep = 1

[pcp metrics]
  hello.world =

[pcp]
  snapshot = /tmp

[actions]
  install = pkg:100 download:false io:true

[section]
  # Comment
  key = value

[other section]
  # Another comment
  key = another value

        """
        os_handle, self.scenario = tempfile.mkstemp()
        scenario_handle = open(self.scenario, 'w')
        scenario_handle.write(scenario_src)
        scenario_handle.close()

        self.cfg = ConfigParser.ConfigParser()
        self.cfg.readfp(loadproc.ScenarioPreprocessor(self.scenario))

    def tearDown(self):
        """
        Finish a test case.

        :return:
        """
        os.unlink(self.scenario)

    def test_sections(self):
        """
        Test sections

        :return:
        """
        for section in ['section', 'other section']:
            self.assertTrue(section in self.cfg.sections())

    def test_items(self):
        """
        Test config items are properly placed.

        :return:
        """
        for section, key, value in (('section', 'key', 'value'),
                                    ('other section', 'key', 'another value'),
                                    ('pcp metrics', 'hello.world', 'void')):
            self.assertTrue(key in self.cfg.options(section))
            self.assertTrue(len(self.cfg.options(section)) == 1)
            self.assertTrue(self.cfg.get(section, key) == value)

    def test_scenario_caller(self):
        """
        Scenario caller.

        :return:
        """
        caller = loadproc.LoadScenarioCaller(None)
        caller.load_scenario(self.scenario)
        scenario = caller._scenario[0]
        self.assertTrue('args' in scenario)
        self.assertTrue('method' in scenario)
        self.assertTrue(scenario['method'] == 'install')
        self.assertTrue('kwargs' in scenario)
        self.assertTrue('download' in scenario['kwargs'])
        self.assertTrue(not scenario['kwargs']['download'])
        self.assertTrue(int(scenario['kwargs']['pkg']) == 100)
        self.assertTrue(scenario['kwargs']['io'])


