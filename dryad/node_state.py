"""
    Name: node_state.py
    Author: Francis T
    Desc: Source code for cache node state info object
"""

import logging
from threading import Lock

NODE_STATES = [
    "UNKNOWN",
    "INACTIVE",
    "IDLE",
    "SCANNING",
    "GATHERING",
    "SAVING"
]

class NodeState():
    def __init__(self):
        self.state = "UNKNOWN"
        self.state_lock = Lock()
        self.logger = logging.getLogger("NodeState")
        return

    def set_state(self, state):
        self.state_lock.acquire()
        if state.upper() in NODE_STATES:
            self.state = state.upper()
            self.state_lock.release()
            self.logger.debug("State Changed: {}".format(state))
            return True

        self.logger.error("Invalid state: {}".format(state))
        self.state_lock.release()
        return False
    
    def get_state(self):
        self.state_lock.acquire()
        state = self.state
        self.state_lock.release()
        return str(state)




