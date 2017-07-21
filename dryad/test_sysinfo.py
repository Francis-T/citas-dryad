import unittest
import time
import sys_info


class TestSysInfo(unittest.TestCase):
    # Executed before each test method
    def setUp(self):
        pass

    # Executed after each test method
    def tearDown(self):
        pass

    def test_set_params(self):
        self.assertEqual( sys_info.set_param("PARM1", "A"), True )
        self.assertEqual( sys_info.set_param("PARM2", "B"), True )

        self.assertNotEqual( sys_info.get_param("PARM1"), False )
        self.assertNotEqual( sys_info.get_param("PARM2"), False )
        self.assertEqual( sys_info.get_param("PARM3"), False )

        return

    def test_set_info(self):
        self.assertEqual( sys_info.set_info("INFO1", "A"), True )
        self.assertEqual( sys_info.set_info("INFO2", "B"), True )

        self.assertNotEqual( sys_info.get_info("INFO1"), False )
        self.assertNotEqual( sys_info.get_info("INFO2"), False )
        self.assertEqual( sys_info.get_info("PARM1"), False )
        self.assertEqual( sys_info.get_info("INFO3"), False )

        return

if __name__ == '__main__':
    unittest.main()

