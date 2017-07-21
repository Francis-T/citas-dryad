#
#   Status Indicator Circuit Controller
#   Author: Francis T
#
#   Controls the status indicator circuit to reflect the current state 
#   of the aggregator node
#

from time import sleep
# import RPi.GPIO as GPIO
import dummy_gpio as GPIO

STATUS_INACTIVE = 0
STATUS_READY    = 1
STATUS_BUSY     = 2
STATUS_SHUTDOWN = 3
STATUS_TX       = 4
STATUS_RX       = 5

PIN_ACTIVE      = 22
PIN_BUSY        = 23
PIN_TXRX        = 24

def initialize():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN_ACTIVE,  GPIO.OUT)
        GPIO.setup(PIN_BUSY,    GPIO.OUT)
        GPIO.setup(PIN_TXRX,    GPIO.OUT)
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

def set_pins(a=0, b=0, c=0):

    if (a == 1):
        GPIO.output(PIN_ACTIVE, GPIO.HIGH)
    elif (a == 0):
        GPIO.output(PIN_ACTIVE, GPIO.LOW)

    if (b == 1):
        GPIO.output(PIN_BUSY, GPIO.HIGH)
    elif (b == 0):
        GPIO.output(PIN_BUSY, GPIO.LOW)

    if (c == 1):
        GPIO.output(PIN_TXRX, GPIO.HIGH)
    elif (c == 0):
        GPIO.output(PIN_TXRX, GPIO.LOW)

    return

def indicate(status):
    success = True

    if ( initialize() != True ):
        return False

    if (status == STATUS_INACTIVE):
        set_pins(0, 0, 0)

    elif (status == STATUS_READY):
        set_pins(1, 0, 0)

    elif (status == STATUS_BUSY):
        set_pins(1, 1, 0)

    elif (status == STATUS_SHUTDOWN):
        for n in range(0, 3):
            set_pins(1, 0, 0)
            sleep(1.0)

            set_pins(0, 0, 0)
            sleep(1.0)

    elif ( (status == STATUS_TX) or (status == STATUS_RX) ):
        set_pins(-1, -1, 1)
        sleep(0.25)
        set_pins(-1, -1, 0)

    else:
        success = False
    
    if ( cleanup() != True ):
        return False

    return success

