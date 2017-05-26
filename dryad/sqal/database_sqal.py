import logging

from models import Base, NodeData, NodeEvent, SystemInfo
from models import Node, SystemParam, NodeDevice, Session

from sqlalchemy import create_engine, event, and_
from sqlalchemy.orm import sessionmaker

import time

DEFAULT_DB_NAME = "sqlite:///dryad_cache.db"
module_logger = logging.getLogger("main.database")


class DryadDatabase:
    def __init__(self, db_name=DEFAULT_DB_NAME):
        self.engine = create_engine(db_name)

        event.listen(self.engine, 'connect', self.on_connect)
        DBSession = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

        # Current db session
        self.db_session = DBSession()

    def close_session(self):
        try:
            self.db_session.close()
        except Exception as e:
            print(e)
            return False
        return True

    # Required in order to add foreign keys constraints
    def on_connect(self, conn, record):
        conn.execute('pragma foreign_keys=ON')

    # Executes each test case
    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    ##********************************##
    ##          Utilities             ##
    ##******************************* ##
    # @desc     Adds a record
    # @return   True if successful, otherwise False
    def add(self, row):
        try:
            self.db_session.add(row)
            self.db_session.commit()
        except Exception as e:
            print(e)
            return False
        return True

    # @desc     Inserts if record non-existing, update if otherwise
    # @return   True if successful, otherwise False
    def insert_or_update(self, obj):
        try:
            self.db_session.merge(obj)
            self.db_session.commit()
        except Exception as e:
            print(e)
            return False
        return True

    # @desc     Gets a record
    # @return   True if successful, otherwise False
    def get(self, field, result):
        if result is not None:
            return result

        print("Get: Non-existing {}.".format(field))
        return False

    # @desc     Deletes a record
    # @return   True if successful, otherwise False
    def delete(self, obj):
        try:
            self.db_session.delete(obj)
        except Exception as e:
            print(e)
            return False

        return True

    ##********************************##
    ##        System Parameters       ##
    ##******************************* ##
    def insert_or_update_system_param(self, name=None, value=""):
        sys_param = SystemParam(name=name, value=value)
        return self.insert_or_update(sys_param)

    def insert_or_update_system_info(self, name=None, value=""):
        sys_info = SystemInfo(name=name, value=value)
        return self.insert_or_update(sys_info)

    def get_system_param(self, name):
        result = self.db_session.query(
            SystemParam).filter_by(name=name).first()
        return self.get(field=name, result=result)

    def get_system_info(self, name):
        result = self.db_session.query(
            SystemInfo).filter_by(name=name).first()
        return self.get(field=name, result=result)

    ##********************************##
    ##              Node              ##
    ##******************************* ##
    def insert_or_update_node(self, name, node_class, site_name, lat, lon):
        node = Node(name=name, node_class=node_class, site_name=site_name,
                    lat=lat, lon=lon)
        return self.insert_or_update(node)

    def get_nodes(self, name=None, node_class=None):
        if name is not None and node_class is not None:
            result = self.db_session.query(
                Node).filter(and_(name=name, node_class=node_class)).first()
        elif name is not None:
            result = self.db_session.query(
                Node).filter_by(name=name).first()
        elif node_class is not None:
            result = self.db_session.query(
                Node).filter_by(node_class=node_class).all()
        else:
            result = self.db_session.query(
                Node).all()

        return self.get(name, result)

    def delete_node(self, name):
        result = self.get_node(name)
        return self.delete(result)

    ##********************************##
    ##            Device              ##
    ##******************************* ##
    def insert_or_update_device(self, address, node_id, device_type):
        node_device = NodeDevice(address=address, node_id=node_id,
                                 device_type=device_type)
        return self.insert_or_update(node_device)

    def get_device(self, address):
        result = self.db_session.query(
            NodeDevice).filter_by(address=address).first()
        return self.get(address, result)

    def delete_device(self, name):
        result = self.get_device(name)
        return self.delete(result)

    ##********************************##
    ##           Session              ##
    ##******************************* ##
    def start_session(self):
        session = Session(start_time=str(int(time.time())), end_time=-1)
        return self.add(session)

    def get_current_session(self):
        try:
            result = self.db_session.query(Session).order_by(
                Session.id.desc()).filter(Session.end_time == -1)[-1]
        except Exception as e:
            print("No available open session")
            return False
        return result

    def terminate_session(self):
        result = self.get_current_session()
        if result is False:
            return False
        result.end_time = str(int(time.time()))
        self.db_session.commit()
        return True

    ##********************************##
    ##              Data              ##
    ##******************************* ##
    def get_data(self, id=None, session_id=None, limit=None, offset=None,
                 start_id=0, end_id=100000000000000):

        result = self.db_session.query(NodeData.id, Node.name,
                                       Session.end_time, NodeData.content,
                                       Node.lat, Node.lon, Node.site_name)\
            .join(Node, Session).filter(
                and_(NodeData.id >= start_id, NodeData.id <= end_id)).order_by(
                NodeData.id)

        if offset is not None:
            result = result[offset:]
        if limit is not None:
            result = result[:limit]
        return result

    def add_data(self, source_id, content, timestamp):
        data = NodeData(session_id=self.get_current_session().id, source_id=source_id,
                        content=content, timestamp=timestamp)

        return self.add(data)

    ##********************************##
    ##             Event              ##
    ##******************************* ##
    def add_event(self, node_id, event_type, timestamp):
        event = NodeEvent(
            node_id=node_id, event_type=event_type, timestamp=timestamp)
        return self.add(event)

    def get_event(self, id):
        result = self.db_session.query(NodeEvent).filter_by(id=id).first()
        return result

    def delete_event(self, id):
        result = self.get_event(id)
        return self.delete(result)
