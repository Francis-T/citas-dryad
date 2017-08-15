import logging
import time

from collections import Iterable
from sqlalchemy import create_engine, event, and_
from sqlalchemy.orm import sessionmaker

from dryad.models import Base, NodeData, NodeEvent, SystemInfo
from dryad.models import Node, SystemParam, NodeDevice, Session
from dryad.models import SessionData


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

            # If the result is already a list, we can return it immediately
            if type(result) is list:
                return result

            # If it is an iterable, transform it into a Python list
            if isinstance(result, Iterable):
                return result.all()

            # Otherwise, encapsulate it in a Python list
            return [ result ]

        print("Get: Non-existing {}.".format(field))
        return False

    # @desc     Deletes a record
    # @return   True if successful, otherwise False
    def delete(self, obj):
        try:
            self.db_session.delete(obj)
            self.db_session.commit()
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

    def get_all_system_params(self):
        result = self.db_session.query(SystemParam).all()
        return self.get("sys_params", result)

    def get_all_system_info(self):
        result = self.db_session.query(SystemInfo).all()
        return self.get("sys_info", result)

    ##********************************##
    ##              Node              ##
    ##******************************* ##
    def insert_or_update_node(self, name, node_class, site_name=None, lat=None, lon=None):
        node_lat  = lat
        node_lon  = lon
        node_site = site_name

        matched_nodes = self.get_nodes(name)
        if matched_nodes != False:
            if len(matched_nodes) <= 0:
                node_lat = 0.0
                node_lon = 0.0
                site_name = "????"

            else:
                # Attempt to reload the old parameters if ever there are none supplied
                if lat == None:
                    node_lat  = matched_nodes[0].lat

                if lon == None:
                    node_lon  = matched_nodes[0].lon

                if site_name == None:
                    node_site = matched_nodes[0].site_name
            
        node = Node(name=name, node_class=node_class, 
                    site_name=node_site, lat=node_lat, lon=node_lon)
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
        matched_nodes = self.get_nodes(name=name)

        if len(matched_nodes) <= 0:
            print("No nodes matched: {}".format(name))
            return False

        target_node = matched_nodes[0]

        return self.delete(target_node)

    ##********************************##
    ##            Device              ##
    ##******************************* ##
    def insert_or_update_device(self, address, node_id, device_type, power=-99.0):
        node_device = NodeDevice(address=address, node_id=node_id,
                                 device_type=device_type, power=power)
        return self.insert_or_update(node_device)

    def get_devices(self, name=None, address=None, device_type=None):
        target = self.db_session.query(NodeDevice)

        if address is not None:
            target = target.filter_by(address=address).first()

        if device_type is not None:
            target = target.filter_by(device_type=device_type).all()
        
        if name is not None:
            target = target.filter_by(node_id=name).all()

        return self.get(address, target)

    def delete_device(self, name):
        matched_devices = self.get_devices(name=name)
        if len(matched_devices) <= 0:
            return False

        result = True
        for target_device in matched_devices:
            if self.delete(target_device) == False:
                result = False

        return result

    ##********************************##
    ##           Session              ##
    ##******************************* ##
    def start_session(self):
        session = Session(start_time=str(int(time.time())), end_time=-1)
        print(session)
        return self.add(session)

    def get_current_session(self):
        try:
            result = self.db_session.query(Session).order_by(
                Session.id.desc()).filter(Session.end_time == -1)[-1]
        except Exception as e:
            print("No available open session")
            return False
        return result

    def get_sessions(self, record_offset=0, record_limit=3):
        result = []
        try:
            session_query = self.db_session.query(Session)\
                                .order_by(Session.id.desc())\
                                .limit(record_limit)\
                                .offset(record_offset)

            result = self.get("session_id", session_query)

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
            .join(Session).join(Node, NodeData.source_id == Node.name).filter(
                and_(NodeData.id >= start_id, NodeData.id <= end_id)).order_by(
                NodeData.id)

        if offset is not None:
            result = result[offset:]

        if limit is not None:
            result = result[:limit]

        return self.get("data", result)

    def add_data(self, blk_id, session_id, source_id, content, timestamp):
        data = NodeData(blk_id=blk_id,
                        session_id=session_id,
                        source_id=source_id,
                        content=content, timestamp=timestamp)
        return self.add(data)

    ##********************************##
    ##           Session Data         ##
    ##******************************* ##
    def get_session_data(self, id=None, session_id=None, limit=None, 
                         offset=None, start_id=0, end_id=100000000000000):
    
        
        result = self.db_session.query(SessionData.id, 
                                       SessionData.session_id, 
                                       SessionData.source_id, 
                                       SessionData.content,
                                       SessionData.timestamp)\
                                .filter(and_(SessionData.id >= start_id, 
                                             SessionData.id <= end_id))\
                                .order_by(SessionData.source_id, SessionData.id)

        if offset is not None:
            result = result[offset:]
        if limit is not None:
            result = result[:limit]
        return self.get("data", result)

    def add_session_data(self, source_id, content, timestamp):
        data = SessionData(session_id=self.get_current_session().id, 
                           source_id=source_id,
                           content=content, 
                           timestamp=timestamp)
        return self.add(data)

    def clear_session_data(self):
        self.db_session.query(SessionData).delete()
        self.db_session.commit()

        return True


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

