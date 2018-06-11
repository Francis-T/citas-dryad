import serial
import time
import datetime


ser = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=None)
print(ser.name)
while True:
    try:
        reading = ser.readline().decode("utf-8").strip()
        print(reading)
        if not reading.startswith('{') and not reading.endswith('}'):
            continue
        packet = eval(reading)

    except Exception as e:
        print("Exception occured {}".format(str(e)))
        continue

    print(packet)
#    print(packet['Header'].keys())

    #print(datetime.datetime.fromtimestamp(int(packet['Header']['Timestamp'])).strftime('%Y-%m-%d %H:%M:%S'))
    #if packet['Header']['Type'] == 1:
    #    print("Power: {}".format(packet['Status']['Power']))
    #elif packet['Header']['Type'] == 2:
    #    print("Moisture: {}".format(packet['Data']['Moisture']))
        

ser.close()

