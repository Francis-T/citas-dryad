
"""
    Locates nearby BLE-based Sensor Nodes by conducting a BLE scan / discovery
"""
def find_sensor_nodes():
    devices = {};
    device_count = 0
    trial_count = MAX_TRIAL_COUNT
    while device_count < 1:
        logger.info("Looking for devices...")
        devices = ble.scan_for_devices(2)
        device_count = len(devices.items())
        logger.info("Found {} device/s".format(device_count))
        if device_count == 0:
            trial_count -= 1
            if trial_count < 0:
                logger.info("Could not find any nearby sensor nodes!")
                break
        time.sleep(1.5)
    return devices

found_devices = find_sensor_nodes()

print("Devices found: ")
index = 0
for addr, name in found_devices.items():
    print("#{}: Name = {}, Address = {}".format(index, name, addr))

print("Enter index of device to test: ")
sel_dvc_idx = raw_input(">")




