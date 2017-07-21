#
#   Wakeup Circuit Controller
#   Author: Francis T
#
#   Interfaces with the wakeup circuit which provides and cuts off power to 
#   the aggregator node's Raspberry Pi
#

import dummy_gpio as GPIO

PIN_SHUTDOWN_NOTIF = 25

def initialize():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_SHUTDOWN_NOTIF,  GPIO.OUT)
    except Exception as e:
        # @log exception occurred
        return False

    return True

def cleanup():
    try:
        GPIO.cleanup()
    except Exception as e:
        # @log exception occurred
        return False

    return True

def notify_shutdown(self):
    GPIO.output(PIN_SHUTDOWN_NOTIF, GPIO.HIGH)
    return True

