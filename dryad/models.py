"""
    Name: models.py
    Author: Jerelyn C
    Description:
        Database models using SQLAlchemy
"""

import enum

from sqlalchemy import Integer, String, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, event

Base = declarative_base()

# Validation functions


def validate_int(value):
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            raise AttributeError("Value cant be assigned to integer")
    else:
        if not isinstance(value, int):
            raise AttributeError("Value cant be assigned to integer")
    return value


def validate_string(value):
    if not isinstance(value, str):
        raise AttributeError("Value cant be assigned to string")
    return value


validators = {
    Integer: validate_int,
    String: validate_string,
}


# Validators when creating and inserting new objects
@event.listens_for(Base, 'attribute_instrument')
def configure_listener(class_, key, inst):
    if not hasattr(inst.property, 'columns'):
        return

    # event called whenever a "set" occurs on that instrumented attribute
    @event.listens_for(inst, "set", retval=True)
    def set_(instance, value, oldvalue, initiator):
        validator = validators.get(inst.property.columns[0].type.__class__)
        if validator:
            return validator(value)
        else:
            return value

# Enums for the node classes and events


class EnumWsnClass(enum.Enum):
    AGGREGATOR = "AGGREGATOR"
    RELAY = "RELAY"
    SENSOR = "SENSOR"
    MOBILE = "MOBILE"
    SELF = "SELF"
    UNKNOWN = "UNKNOWN"


class EnumEvents(enum.Enum):
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    SCAN = "SCAN"


class SystemParam(Base):
    __tablename__ = 't_sys_params'
    # id = Column(Integer, primary_key=True)
    name = Column(String, primary_key=True)
    value = Column(String, nullable=True)

    def __repr__(self):
        return "<SystemParam(name={}, value={}>".format(
            self.name, self.value)


class SystemInfo(Base):
    __tablename__ = 't_sys_info'
    # id = Column(Integer, primary_key=True)
    name = Column(String, primary_key=True)
    value = Column(String, nullable=False)

    def __repr__(self):
        return "<SystemInfo(name={}, value={}>".format(self.name, self.value)


class Session(Base):
    __tablename__ = 't_sessions'
    id = Column(Integer, primary_key=True)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer)

    def __repr__(self):
        return "<Session(id={}, start_time={}, \
        end_time={}>".format(self.id, self.start_time, self.end_time)


class Node(Base):
    __tablename__ = 't_nodes'
    # id = Column(Integer, primary_key=True)
    address = Column(String, primary_key=True)
    name = Column(String)
    node_class = Column(Enum(EnumWsnClass, validate_strings=True))
    site_name = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    power = Column(Float)

    def __repr__(self):
        return "<Node(name={}, node_class={}, site_name={}, \
        lat={}, lon={}, power={}>".format(self.name, self.node_class, self.site_name,
                                self.lat, self.lon, self.power)


class NodeData(Base):
    __tablename__ = 't_node_data'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('t_sessions.id'))
    source_id = Column(String)
    dest_id = Column(String)
    part = Column(String)
    length = Column(Integer)
    content = Column(String)
    timestamp = Column(Integer)

    session = relationship("Session")

    def __repr__(self):
        return "<NodeData(id={}, session_id={}, source_id={}, dest_id={}, part={}, \
        content={}, timestamp={}>".format(self.id, self.session_id, self.source_id,
                                          self.dest_id, self.part, self.content,
                                          self.timestamp)


class SessionData(Base):
    __tablename__ = 't_session_data'
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('t_sessions.id'))
    source_id = Column(String)
    content = Column(String)
    timestamp = Column(Integer)

    session = relationship("Session")

    def __repr__(self):
        return "<SessionData(id={}, session_id={}, source_id={}, content={}, \
        timestamp={}>".format(self.id, self.session_id, self.source_id,
                              self.content, self.timestamp)


class NodeEvent(Base):
    __tablename__ = 't_node_events'
    id = Column(Integer, primary_key=True)
    node_id = Column(String, ForeignKey('t_nodes.name'))
    event_type = Column(Enum(EnumEvents, validate_strings=True))
    timestamp = Column(Integer)

    node = relationship("Node")

    def __repr__(self):
        return "<NodeEvent(id={}, node_id={}, event_type={}, \
        timestamp={}>".format(self.id, self.node_id, self.event_type,
                              self.timestamp)


class Exception(Base):
    __tablename__ = 't_exception'
    id = Column(Integer, primary_key=True)
    message = Column(String)

    def __repr__(self):
        return "<Exception(id={}, message={}>".format(self.id, self.message)
