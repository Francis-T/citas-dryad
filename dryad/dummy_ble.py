from threading import Thread, Event, active_count
from time import sleep

class ReadCompletionWaitTask(Thread):
    def __init__(self, evt, wait_time=2.0):
        Thread.__init__(self)
        self.hevent = evt
        self.wait_time = wait_time
        return

    def run(self):
        sleep(self.wait_time)
        self.hevent.set()

        return

    def cancel(self):
        return

class Dummy():
    def __init__(self, addr, name, evt, emulate=None):
        self.hevent = evt
        self.emulate = emulate
        return

    def stop(self):
        return

    def set_max_samples(self, n):
        return

    def start(self, read_until=None):
        task_read_complete = ReadCompletionWaitTask(self.hevent, self.wait_time)
        task_read_complete.start()
        return

    def stop(self):
        return

    def get_readings(self):
        if self.emulate == "PARROT":
            return ????
        elif self.emulate == "BLUNO":
            return ???

        return None



