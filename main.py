#   Dryad Main
#   Author: Francis T
#
#   Source code for the "main" point-of-entry into the program
#
import logging

from threading import Event, Thread
from dryad.mobile_node.link_listener import LinkListenerThread
from dryad.flask_link.flask_listener import FlaskListenerThread
from dryad.mobile_node.request_handler import RequestHandler
from dryad.aggregator_node.core import AggregatorNode

VERSION = "2.0.0"
DEBUG_CONSOLE_ENABLED = False

class DummyLink():
    def __init__(self):
        return

    def send_response(self, content):
        print("<<< {}".format(content))
        return

class InputThread(Thread):
    def __init__(self, receiver, request_handler):
        Thread.__init__(self)
        self.receiver = receiver
        self.request_handler = request_handler
        self.is_running = False

        # TODO Dummy Classes
        self.link = DummyLink()
        return

    def run(self):
        self.is_running = True
        while self.is_running:
            cmd = input("> ")
            if (cmd == "QUIT"):
                self.receiver.stop()
                is_running = False
                break

            elif cmd.startswith("# "):
                request = cmd.replace("# ","")
                self.request_handler.handle_request(self.link, request)

            else:
                self.receiver.add_task(cmd)

        return

    def cancel(self):
        self.is_running = False
        return


class DryadMain():
    def __init__(self):
        return

    def init_logger(self):
        self.logger = logging.getLogger("main")
        self.logger.setLevel(logging.DEBUG)

        # console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # formatter
        formatter = logging.Formatter("%(asctime)s - [%(levelname)s] [%(threadName)s] (%(module)s:%(lineno)d) %(message)s") 
     
        fh = logging.FileHandler("cache_node.log")

        # ch setting
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)   

        # fh setting
        fh.setFormatter(formatter)
        self.logger.addHandler(fh) 

        return

    def run(self):
        self.init_logger()

        completion_event = Event()

        # Initialize the main Aggregator Node module
        agn = AggregatorNode()
        agn.start(completion_event)

        # Instantiate the Request Handler module
        rqh = RequestHandler(agn)

        # Initialize the Bluetooth EDR Link Listener Thread
        listen_thread = LinkListenerThread(rqh)
        listen_thread.start()

        # Initialize the Flask Listener Thread
        flask_listen_thread = FlaskListenerThread(rqh)
        flask_listen_thread.start()

        # Initialize the Console Input Thread
        if DEBUG_CONSOLE_ENABLED:
            input_thread = InputThread(agn, rqh)
            input_thread.start()

        # Wait for the Aggregator Node to close down
        completion_event.wait()

        # Get the AGN exit code
        result = agn.get_exit_code()

        # Cancel the other threads
        if DEBUG_CONSOLE_ENABLED:
            input_thread.cancel()

        flask_listen_thread.cancel()
        listen_thread.cancel()

        return result

if __name__ == "__main__":
    test = DryadMain()
    result = test.run()
    exit(result)
        

