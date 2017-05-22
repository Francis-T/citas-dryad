import unittest
import time
from dryad.database_sqal import DryadDatabase


class TestDatabase(unittest.TestCase):
    # Executed before each test method
    def setUp(self):
        self.ddb = DryadDatabase(test_session=True)

    # Executed after each test method
    def tearDown(self):
        self.ddb.tearDown()
        # pass

    # Required in order to add foreign keys constraints
    def on_connect(self, conn, record):
        conn.execute('pragma foreign_keys=ON')

    def check_success(self, rows):
        for row in rows:
            self.assertEqual(row[0], row[1])

    def test_system_param_info(self):
        test_sys_params = [
            (self.ddb.insert_or_update_system_param(
                name="param2", value="val2"), True),
            (self.ddb.insert_or_update_system_param(
                name="par3", value="val3"), True),
            (self.ddb.insert_or_update_system_param(
                name="par3", value="updated_val3"), True),
        ]

        self.check_success(test_sys_params)

        self.assertEqual(self.ddb.get_system_param(
            name="par3").value, "updated_val3")

        test_sys_info = [
            (self.ddb.insert_or_update_system_info(
                name="info1", value="val1"), True),
            (self.ddb.insert_or_update_system_info(
                name="info2", value="val2"), True),
            (self.ddb.insert_or_update_system_info(
                name="info2", value="updated_val2"), True),
        ]

        self.check_success(test_sys_info)

        self.assertEqual(self.ddb.get_system_info(
            name="info2").value, "updated_val2")

    def test_node_device(self):
        test_nodes = [
            (self.ddb.insert_or_update_node(
                name="RPI01", node_class="AGGREGATOR", site_name="GS01",
                lat=14.01, lon=123.45056), True),
            (self.ddb.insert_or_update_node(
                name="SN01", node_class="SENSOR", site_name="GS01",
                lat=14.024, lon=123.45057), True),
            (self.ddb.insert_or_update_node(
                name="SN02", node_class="SENSOR", site_name="GS02",
                lat=14.156, lon=123.45057), True),
            # SN02 site name should update
            (self.ddb.insert_or_update_node(
                name="SN02", node_class="SENSOR", site_name="GS01",
                lat=14.156, lon=123.45057), True),
        ]
        self.check_success(test_nodes)

        result = self.ddb.get_node("SN01")
        self.assertEqual(result.site_name, "GS01")

        test_device = [
            (self.ddb.insert_or_update_device(
                address="AG42GD3550", node_id="SN02",
                device_type="BLUNO"), True),
            (self.ddb.insert_or_update_device(
                address="AG42GD3550", node_id="SN02",
                device_type="PARROT"), True),
            # Invalid device type
            (self.ddb.insert_or_update_device(
                address="AG42GD3560", node_id="SN02",
                device_type="INVALID"), False),
            # Non-existing SN03
            (self.ddb.insert_or_update_device(
                address="AG42GD3560", node_id="SN03",
                device_type="PARROT"), False),
        ]

        self.check_success(test_device)

        # Rollback from error
        self.ddb.db_session.rollback()

        # Checking device type update
        result = self.ddb.get_device(address="AG42GD3550")
        self.assertEqual(result.device_type.name, "PARROT")

    def test_event(self):
        test_nodes = [
            (self.ddb.insert_or_update_node(
                name="SN01", node_class="SENSOR", site_name="GS01",
                lat=14.024, lon=123.45057), True),
        ]
        self.check_success(test_nodes)

        test_events = [
            (self.ddb.add_event(node_id="SN01",
                                event_type="CONNECT",
                                timestamp=int(time.time())), True)
        ]
        self.check_success(test_events)

        self.assertEqual(self.ddb.get_event(id=1).event_type.name, "CONNECT")
        self.assertEqual(self.ddb.delete_event(id=1), True)

    def test_data(self):
        # insert_or_updateting of nodes
        test_nodes = [
            (self.ddb.insert_or_update_node(
                name="RPI01", node_class="AGGREGATOR", site_name="GS01",
                lat=14.01, lon=123.45056), True),
            (self.ddb.insert_or_update_node(
                name="SN01", node_class="SENSOR", site_name="GS01",
                lat=14.024, lon=123.45057), True),
            (self.ddb.insert_or_update_node(
                name="SN02", node_class="SENSOR", site_name="GS02",
                lat=14.156, lon=123.45057), True),
        ]
        self.check_success(test_nodes)

        # Starting a session
        self.ddb.start_session()

        # Adding data
        test_data = [
            (self.ddb.add_data(source_id="SN01",
                               content="{'pH':7.5, 'temp':32}",
                               timestamp=1495434438), True),
            (self.ddb.add_data(source_id="SN02",
                               content="{'pH':10.5, 'temp':32}",
                               timestamp=1495434468), True),
            (self.ddb.add_data(source_id="SN02",
                               content="{'pH':12.5, 'temp':32}",
                               timestamp=1495434488), True),
            (self.ddb.add_data(source_id="SN02",
                               content="{'pH':13.5, 'temp':37}",
                               timestamp=1495434588), True),
            (self.ddb.add_data(source_id="SN01",
                               content="{'pH':8, 'temp':28}",
                               timestamp=1495434448), True),
            (self.ddb.add_data(source_id="SN02",
                               content="{'pH':6, 'temp':28}",
                               timestamp=1495434248), True),
        ]

        self.check_success(test_data)

        # Terminating a session
        self.ddb.terminate_session()

        # Tests: Getting data
        query_result = self.ddb.get_data(offset=3)
        self.assertEqual(len(query_result), 3)
        self.assertEqual(query_result[0].id, 4)
        self.assertEqual(query_result[-1].id, 6)

        query_result = self.ddb.get_data(offset=2, limit=3)
        self.assertEqual(len(query_result), 3)
        self.assertEqual(query_result[0].id, 3)
        self.assertEqual(query_result[-1].id, 5)


if __name__ == '__main__':
    unittest.main()
