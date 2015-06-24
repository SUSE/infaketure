#!/usr/bin/python
#
"""
Main unittest runner.
"""
__author__ = 'bo'

import unittest
import sys
from surrogate import surrogate
from mock import Mock


@surrogate('up2date_client.up2dateErrors')
@surrogate('up2date_client.up2dateLog')
@surrogate('up2date_client.up2dateUtils')
@surrogate('up2date_client.config')
@surrogate('up2date_client.rpcServer')
@surrogate('up2date_client.rhnserver')
@surrogate('up2date_client.clientCaps')
@surrogate('up2date_client.capabilities')
@surrogate('up2date_client.rhncli')
@surrogate('up2date_client.rhnreg')
def main():
    """
    Test suite runner
    :return:
    """
    sys.path.append("../")
    import up2date_client

    up2date_client.up2dateLog.initLog = Mock(return_value=None)
    up2date_client.rhnserver.RhnServer = Mock(return_value=None)
    up2date_client.rhncli.RhnCli = Mock(return_value=None)

    from tests.test_actions import TestActions
    from tests.test_sqlite import TestSQLiteHandler
    from tests.test_scenario_loader import TestScenarioLoader

    unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
        unittest.TestLoader().loadTestsFromTestCase(TestSQLiteHandler),
        unittest.TestLoader().loadTestsFromTestCase(TestActions),
        unittest.TestLoader().loadTestsFromTestCase(TestScenarioLoader),
    ]))

if __name__ == "__main__":
    main()
