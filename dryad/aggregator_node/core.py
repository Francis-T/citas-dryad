#
#   Aggregator Node Class
#   Author: Francis T and Jerelyn C
#
#   Class for all Aggregator Node functionality
#
import logging
import dryad.sys_info as sys_info

from time import time
from queue import Queue
from threading import Event, Timer, Lock, Thread
from dryad.aggregator_node.collect_thread import CollectThread
from dryad.aggregator_node.network import BaseAggregatorNodeNetwork
from dryad.external_switches import ExternalSwitch

TASK_EVENT_TIMEOUT      = 120.0

RESULT_FATAL    = -3
RESULT_SHUTDOWN = -2
RESULT_FAIL     = -1
RESULT_UNKNOWN  = 0
RESULT_OK       = 1

STATE_UNKNOWN       = 0
STATE_TERMINATING   = 1
STATE_INACTIVE      = 2
STATE_IDLE          = 3
STATE_SCANNING      = 4
STATE_GATHERING     = 5
STATE_SAVING        = 6

STATUS_NOT_DEPLOYED = 0
STATUS_DEPLOYED     = 1

NODE_STATE_STR = [
    "UNKNOWN",
    "TERMINATING",
    "INACTIVE",
    "IDLE",
    "GATHERING",
    "SAVING"
]

VERSION = "2.0.1"
COLLECTION_INTERVAL = 60.0 * 60.0
IDLE_OUT_INTERVAL   = 60.0 * 20.0
NET_UPDATE_INTERVAL  = 60.0 * 60.0 * 24.0

# Exit codes
EXIT_NORMAL     = 0
EXIT_ERROR      = 1
EXIT_RELOAD     = 2
EXIT_REBOOT     = 3
EXIT_POWEROFF   = 4
EXIT_SUSPEND    = 5

class AggregatorThread(Thread):
    def __init__(self, parent, event_complete=None):
        Thread.__init__(self)
        self.parent = parent
        self.event_complete = event_complete
        return

    def run(self):
        self.parent.await_tasks()

        # TODO Notify that the thread is finished
        if (self.event_complete != None):
            self.event_complete.set()

        return

class AggregatorNode(BaseAggregatorNodeNetwork):
    def __init__(self):
        BaseAggregatorNodeNetwork.__init__(self)

        self.logger = logging.getLogger("main.AggregatorNode")

        self.task_queue = Queue()
        self.task_event = Event()
        self.task_lock = Lock()
        self.task_tbl = [
            { "id" : "ACTIVATE",      "func" : self.activate_node },
            { "id" : "DEACTIVATE",    "func" : self.deactivate_node },
            { "id" : "SET_PARAMS",    "func" : self.set_system_params },
            { "id" : "START_COLLECT", "func" : self.start_data_collection },
            { "id" : "STOP_COLLECT",  "func" : self.stop_data_collection },
            { "id" : "NET_UPDATE",    "func" : self.update_network },
            { "id" : "EXTEND_IDLE",   "func" : self.extend_idle_period },
            { "id" : "END_IDLE",      "func" : self.idle_out },
            { "id" : "SUSPEND",       "func" : self.suspend_node },
            { "id" : "RELOAD",        "func" : self.reload_node },
            { "id" : "REBOOT",        "func" : self.reboot_node },
            { "id" : "SHUTDOWN",      "func" : self.shutdown_node },
        ]

        self.state = STATE_UNKNOWN
        self.state_lock = Lock()

        self.aggregator_thread = None
        self.collector_thread = None

        self.collection_timer = None
        self.collection_time = None
        self.collection_interval = COLLECTION_INTERVAL

        self.idle_out_timer = None
        self.idle_out_time = None
        self.idle_out_interval = IDLE_OUT_INTERVAL

        self.net_update_interval = NET_UPDATE_INTERVAL

        self.deployment_status = STATUS_NOT_DEPLOYED
        self.exit_code = EXIT_NORMAL

        return

    # Public Functions

    def start(self, event_complete):

        self.set_state(STATE_INACTIVE)

        # Reload aggregator node parameters
        self.reload_system_params()

        # Initialize network records as needed
        self.init_network_records()

        # Reload network information
        self.reload_network_info()

        # Start the aggregator node thread
        self.aggregator_thread = AggregatorThread(self, event_complete)
        self.aggregator_thread.start()

        # Start the idle out timer
        if self.set_idle_out_timer() != RESULT_OK:
            self.logger.error("Failed to set idle out timer")

        #if self.deployment_status == STATUS_DEPLOYED:
        #    # TODO Needs refactoring
        #    self.add_task("ACTIVATE")
        
        ext_sw = ExternalSwitch()
        if (ext_sw.is_node_activated()):
            self.add_task("ACTIVATE")
        else:
            self.add_task("DEACTIVATE")
            
        return

    def stop(self):
        self.add_task("SHUTDOWN")

        return

    def add_task(self, task):
        self.task_lock.acquire()
        self.task_queue.put(task)
        self.task_event.set()
        self.task_lock.release()

        return

    # Private Functions
    def activate_node(self, args=None):
        self.logger.info("[TASK] Activating node")
        self.set_state(STATE_IDLE)

        self.add_task("START_COLLECT")

        self.deployment_status = STATUS_DEPLOYED
        sys_info.set_param("DEPLOYMENT_STATUS", str(STATUS_DEPLOYED))
        
        return RESULT_OK

    def deactivate_node(self, args=None):
        self.logger.info("[TASK] Deativating node")
        self.cancel_collection_timer()

        if self.get_state() <= STATE_IDLE:
            self.set_state(STATE_INACTIVE)

        self.deployment_status = STATUS_NOT_DEPLOYED

        sys_info.set_param("DEPLOYMENT_STATUS", str(STATUS_NOT_DEPLOYED))

        return RESULT_OK

    def start_data_collection(self, args=None):
        self.logger.info("[TASK] Starting data collection")
        self.set_state(STATE_GATHERING)

        # Stop the collection timer if it is running
        self.cancel_collection_timer()

        # Start the data collection thread
        if self.collector_thread == None:
            self.collector_thread = CollectThread(self)
            self.collector_thread.start()

        return RESULT_OK

    def stop_data_collection(self, args=None):
        self.logger.info("[TASK] Stopping data collection")

        # Stop the data collection thread
        if self.collector_thread != None:
            if self.collector_thread.is_alive() == True:
                self.collector_thread.cancel()
                self.collector_thread.join(120.0)

            self.collector_thread = None

        # Stop the collection timer
        self.cancel_collection_timer()

        # Reload aggregator node parameters
        self.reload_system_params()

        # If the node is still deployed, immediately schedule another
        #   collection timer thread to fire back up at a later time
        if self.deployment_status == STATUS_DEPLOYED:
            self.logger.debug("Starting collection timer...")
            if self.set_collection_timer() != RESULT_OK:
                self.logger.error("Failed to set collection timer")
                self.set_state(STATE_INACTIVE)

                return RESULT_FAIL

            self.set_state(STATE_IDLE)

        else:
            self.set_state(STATE_INACTIVE)

        return RESULT_OK

    def update_network(self, args=None):
        self.logger.info("[TASK] Updating network")
        self.set_state(STATE_SCANNING)

        self.set_state(STATE_IDLE)

        return RESULT_OK

    def extend_idle_period(self, args=None):
        self.logger.info("[TASK] Extending idle period")
        return self.set_idle_out_timer()

    def idle_out(self, args=None):
        self.logger.info("System has idled out.")
        return self.shutdown_node(args)

    def suspend_node(self, args=None):
        self.terminate_node()
        self.set_exit_code(EXIT_SUSPEND)
        self.task_event.set()

        return RESULT_OK

    def reload_node(self, args=None):
        self.terminate_node()
        self.set_exit_code(EXIT_RELOAD)
        self.task_event.set()

        return RESULT_OK

    def reboot_node(self, args=None):
        self.terminate_node()
        self.set_exit_code(EXIT_REBOOT)
        self.task_event.set()

        return RESULT_OK

    def shutdown_node(self, args=None):
        self.terminate_node()
        self.set_exit_code(EXIT_POWEROFF)
        self.task_event.set()

        return RESULT_OK

    def terminate_node(self, args=None):
        self.logger.info("System is shutting down")
        self.set_state(STATE_TERMINATING)

        # Cancel active timers
        self.cancel_collection_timer()
        self.cancel_idle_out_timer()

        if self.collector_thread != None:
            self.stop_data_collection()

        return RESULT_OK

    # System Parameter Functions
    def set_system_params(self, args=None):
        self.logger.info("[TASK] Setting system params")

        arg_parts = args[0].split("=", 1)
        if len(arg_parts) != 2:
            return RESULT_FAIL

        param_name  = arg_parts[0]
        param_value = arg_parts[1]

        sys_info.set_param(param_name, str(param_value))

        # Reload our parameters
        self.reload_system_params()

        return RESULT_OK

    def reload_system_params(self):
        reload_idle_out_timer = False
        reload_collection_timer = False

        records = sys_info.get_param("COLLECTION_INTERVAL")
        if records != False:
            new_value = float(records[0].value)
            if abs(new_value - self.collection_interval) > 1:
                reload_collection_timer = True

            self.collection_interval = new_value

        else:
            sys_info.set_param("COLLECTION_INTERVAL", str(COLLECTION_INTERVAL))

        records = sys_info.get_param("IDLE_OUT_INTERVAL")
        if records != False:
            new_value = float(records[0].value)
            if abs(new_value - self.idle_out_interval) > 1:
                reload_idle_out_timer = True

            self.idle_out_interval = new_value

        else:
            sys_info.set_param("IDLE_OUT_INTERVAL", str(IDLE_OUT_INTERVAL))

        records = sys_info.get_param("NET_UPDATE_INTERVAL")
        if records != False:
            self.net_update_interval = float(records[0].value)

        else:
            sys_info.set_param("NET_UPDATE_INTERVAL", str(NET_UPDATE_INTERVAL))

        records = sys_info.get_param("DEPLOYMENT_STATUS")
        if records != False:
            self.deployment_status = int(records[0].value)

        else:
            sys_info.set_param("DEPLOYMENT_STATUS", str(STATUS_NOT_DEPLOYED))

        param_out_str  = "[AGGREGATOR] Parameters: "
        param_out_str += "Collection Interval = {}, "
        param_out_str += "Idle Out Interval = {}, "
        param_out_str += "Net Update Interval = {}, "
        param_out_str += "Deployment Status = {} "
        self.logger.debug(param_out_str.format( self.collection_interval, 
                                                self.idle_out_interval, 
                                                self.net_update_interval, 
                                                self.deployment_status ) )

        if reload_idle_out_timer == True:
            if self.set_idle_out_timer() != RESULT_OK:
                self.logger.error("Failed to set idle out timer")
        
        return

    # Timer Activated Functions
    def add_start_data_collection_task(self):
        self.add_task("START_COLLECT")
        return

    def set_idle_out_timer(self):
        # Cancel the old timer if it exists
        if self.cancel_idle_out_timer() != RESULT_OK:
            self.logger.error("Failed to cancel old idle out timer")
            return RESULT_FAIL

        # Re-create the idle out timer
        self.idle_out_timer = Timer ( self.idle_out_interval,
                                      self.idle_out )
        self.idle_out_timer.start()
        self.idle_out_time = time() + self.idle_out_interval

        return RESULT_OK

    def cancel_idle_out_timer(self):
        if self.idle_out_timer != None:
            if self.idle_out_timer.is_alive():
                self.idle_out_timer.cancel()
                self.idle_out_timer.join(15.0)

            self.idle_out_timer = None

        return RESULT_OK

    def set_collection_timer(self):
        # Cancel the old timer if it exists
        if self.cancel_collection_timer() != RESULT_OK:
            self.logger.error("Failed to cancel old collection timer")
            return RESULT_FAIL

        # Re-create the collection timer
        self.collection_timer = Timer ( self.collection_interval,
                                        self.add_start_data_collection_task )

        # Start the collection timer if the aggregator is currently active
        if self.get_state() > STATE_INACTIVE:
            self.collection_timer.start()

        self.collection_time = time() + self.collection_interval

        return RESULT_OK

    def cancel_collection_timer(self):
        if self.collection_timer != None:
            if self.collection_timer.is_alive():
                self.collection_timer.cancel()
                self.collection_timer.join(15.0)

            self.collection_timer = None

        return RESULT_OK

    # Utility Functions
    def await_tasks(self):
        result = RESULT_UNKNOWN
        while (result >= RESULT_FAIL) and (self.should_continue_running()):
            # If the task queue is empty, then wait for new events to come up
            if self.task_queue.empty():
                self.logger.info("Waiting for tasks...")
                self.task_event.wait(TASK_EVENT_TIMEOUT)
                self.task_event.clear()

                if self.task_queue.empty():
                    self.logger.debug("Timed out.")
                    # Evaluate if we should continue
                    continue

            task = self.task_queue.get()
            try:
                result = self.process_task(task)
            except Exception as e:
                self.logger.exception("Exception Occurred: {}".format(str(e)))
                break

        return

    def process_task(self, task):
        task_part = task.split(" ", 1)
        task_cmd  = task_part[0]
        task_args = None

        # Check if the task has arguments, if so process them
        if len(task_part) == 2:
            task_args = task_part[1].split(",")

        task_func = None
        for known_task in self.task_tbl:
            if task_cmd.startswith(known_task['id']):
                task_func = known_task['func']
                # self.logger.debug("Args: {}".format(task_args))
                break

        if task_func == None:
            self.logger.debug("No handlers found for task: {}".format(task))
            return False
        
        return task_func(task_args)

    def should_continue_running(self):
        if (self.get_state() < STATE_INACTIVE):
            return False

        return True

    def set_state(self, state):
        self.state_lock.acquire()
        if (state > 0) and (state < len(NODE_STATE_STR)):
            self.state = state
            self.logger.debug("[AGGREGATOR] State Changed: {}".format(self.get_state_str()))

        else:
            self.logger.debug("[AGGREGATOR] Invalid State: {}".format(state))

        self.state_lock.release()
        return True
    
    def get_state(self):
        self.state_lock.acquire()
        state = self.state
        self.state_lock.release()
        return state

    def get_state_str(self):
        return NODE_STATE_STR[self.state]

    def get_version(self):
        return VERSION

    def set_exit_code(self, exit_code):
        if exit_code > self.exit_code:
            self.exit_code = exit_code

        return

    def get_exit_code(self):
        return self.exit_code

    def get_idle_out_time(self):
        if self.idle_out_time == None:
            return 0.0

        return self.idle_out_time

    def get_collect_time(self):
        if self.collection_time == None:
            return 0.0

        return self.collection_time

