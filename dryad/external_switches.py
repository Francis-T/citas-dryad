import RPi.GPIO as GPIO

EXT_SW_WIFI_AP_MODE = 23
EXT_SW_ACTV_MODE    = 24

class ExternalSwitch():
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(EXT_SW_WIFI_AP_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(EXT_SW_ACTV_MODE,    GPIO.IN, pull_up_down=GPIO.PUD_UP)

        return

    def is_wifi_mode_active(self):
        # 0 means the switch is shorted to GND
        if (GPIO.input(EXT_SW_WIFI_AP_MODE) == 0):
            return True

        return False

    def is_node_activated(self):
        # 0 means the switch is shorted to GND
        if (GPIO.input(EXT_SW_ACTV_MODE) == 0):
            return True

        return False

    def close(self):
        GPIO.cleanup()
        return


