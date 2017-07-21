#
#   Status Indicator Circuit Controller Test
#   Author: Francis T
#   
#   Tests the status indicator circuit controller
#

import unittest
import status_controller as statc

class BasicFuncTestCase(unittest.TestCase):
    def setUp(self):
        #statc.initialize()
        return

    def test_status_inactive(self):
        self.assertEqual( statc.indicate(statc.STATUS_INACTIVE), True)
        return

    def test_status_ready(self):
        self.assertEqual( statc.indicate(statc.STATUS_READY), True)
        return

    def test_status_busy(self):
        self.assertEqual( statc.indicate(statc.STATUS_BUSY), True)
        return

    def test_status_tx(self):
        self.assertEqual( statc.indicate(statc.STATUS_TX), True)
        return

    def test_status_rx(self):
        self.assertEqual( statc.indicate(statc.STATUS_RX), True)
        return

    def test_status_shutdown(self):
        self.assertEqual( statc.indicate(statc.STATUS_SHUTDOWN), True)
        return

if __name__ == "__main__":
    unittest.main()

