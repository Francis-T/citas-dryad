#
#   Sensor Node Abstract Class
#   Author: Francis T
#
#   Abstract Class used for different types of Sensor Nodes that the 
#   Aggregator Node can interact with
#
from abc import ABCMeta, abstractmethod
from threading import Lock
from dryad.database import DryadDatabase

NODE_STATES = [
    "UNKNOWN",
    "INACTIVE",
    "READING"
]

class BaseSensorNode(metaclass=ABCMeta):
    def __init__(self, node_name, node_address):
        self.name = node_name
        self.addr = node_address
        self.state = "UNKNOWN"
        self.state_lock = Lock()
        return

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def gather_data(self):
        pass

    @abstractmethod
    def stop(self):
        pass


    def get_name(self):
        return self.name

    def get_address(self):
        return self.addr

    def set_state(self, state):
        self.state_lock.acquire()
        if state.upper() in NODE_STATES:
            self.state = state.upper()

        self.state_lock.release()

        return

    def get_state(self):
        self.state_lock.acquire()
        state = self.state
        self.state_lock.release()

        return str(self.state)
        

