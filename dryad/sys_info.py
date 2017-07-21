#
#   System Info Module
#   Author: Francis T
#
#   Utility module abstracting the setting and retrieval of parameter data
#   from the underlying system
#
from dryad.database import DryadDatabase

def get_info(name):
    db = DryadDatabase()
    result = db.get_system_info(name)
    db.close_session()

    return result

def set_info(name, val):
    db = DryadDatabase()
    result = db.insert_or_update_system_info(name, val)
    db.close_session()
    return result

def get_param(name):
    db = DryadDatabase()
    result = db.get_system_param(name)
    db.close_session()

    return result

def set_param(name, val):
    db = DryadDatabase()
    result = db.insert_or_update_system_param(name, val)
    db.close_session()

    return result


