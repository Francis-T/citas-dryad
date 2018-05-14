import serial
import time
import json

from serial.threaded import *

RAW_OUTPUT_FILENAME = "raw.log"
STATUS_OUTPUT_FILENAME = "status.log"
DATA_OUTPUT_FILENAME = "data.log"


PACKET_TYPE_STATUS  = 1
PACKET_TYPE_DATA    = 2

ser = serial.Serial('/dev/ttyACM0', baudrate=115200, timeout=None)
print(ser.name)

# ser.write(b'END\r\n')
data = ""
next_part = ""
while True:
    single_byte = ser.read(1).decode('utf-8')
    bytes_to_read = ser.in_waiting
    data += single_byte
    data += ser.read(bytes_to_read).decode("utf-8")

    if "\n" in data:
        data_part = data.split('\n', 1)
        data = data_part[0]
        next_part = data_part[1]

    else:
        continue

    clean_data = "{" + data.strip().replace("\'", "\"") + "}"
    packet = json.loads( clean_data )

    # Log the raw data to a file
    out_file = open(RAW_OUTPUT_FILENAME, "a")
    out_file.write( clean_data + "\n" )
    out_file.close()

    if "Payload (Status)" == packet['Part']:
        # CSV-ify the data
        #   Timestamp, SourceId, Power, DeploymentState, StatusCode
        csv_str = ""
        csv_str += str(time.ctime())
        csv_str += ", "
        csv_str += str(packet['Content']['Source Node Id'])
        csv_str += ", "
        csv_str += str(packet['Content']['Power'])
        csv_str += ", "
        csv_str += str(packet['Content']['Deployment State'])
        csv_str += ", "
        csv_str += str(packet['Content']['Status Code'])
        csv_str += "\n"

        print("[{}] Power: {}".format(time.ctime(), packet['Content']['Power']))

        # Log the status data to a file
        status_file = open(STATUS_OUTPUT_FILENAME, "a")
        status_file.write( csv_str )
        status_file.close()

    if "Payload (Data)" == packet['Part']:
        # CSV-ify the data
        #   SourceNodeId, DestNodeId, pH, Conductivity, Light, AirTemp, Humidity, SoilTemp, Moisture
        csv_str = ""
        csv_str += str(time.ctime())
        csv_str += ", "
        csv_str += str(packet['Content']['Source Node Id'])
        csv_str += ", "
        csv_str += str(packet['Content']['Dest Node Id'])
        csv_str += ", "
        csv_str += str(packet['Content']['pH'])
        csv_str += ", "
        csv_str += str(packet['Content']['Conductivity'])
        csv_str += ", "
        csv_str += str(packet['Content']['Light'])
        csv_str += ", "
        csv_str += str(packet['Content']['Temp (Air)'])
        csv_str += ", "
        csv_str += str(packet['Content']['Humidity'])
        csv_str += ", "
        csv_str += str(packet['Content']['Temp (Soil)'])
        csv_str += ", "
        csv_str += str(packet['Content']['Moisture'])
        csv_str += "\n"

        print("[{}] Moisture: {}".format(time.ctime(), packet['Content']['Moisture']))
        # Log the status data to a file
        status_file = open(DATA_OUTPUT_FILENAME, "a")
        status_file.write( csv_str )
        status_file.close()

    data = next_part

ser.close()
