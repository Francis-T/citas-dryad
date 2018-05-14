#!/bin/bash

CACHE_NODE_HOME=/home/pi/Programs/citas-dryad/
CACHE_NODE_SCRIPT_LOG=script_exec.log

DETECT_I2C_HWCLK=$(sudo i2cdetect -y -a 1 | grep -e"60" | cut -d' ' -f 10)

EXIT_RELOAD=2
EXIT_REBOOT=3
EXIT_POWEROFF=4

# Wait for ~20 seconds while the RPi boots up
echo -n "Waiting for system to start up...";
if [ "$1" != "-q" ];
then
    for i in {0..20};
    do
        sleep 1;
        echo -n .;
    done;
fi;
echo $'\nDone.'

cd $CACHE_NODE_HOME

if [ ! -f $CACHE_NODE_SCRIPT_LOG ];
then
    touch $CACHE_NODE_SCRIPT_LOG;
fi;

echo "[$(date)] Started." >> $CACHE_NODE_SCRIPT_LOG;

# Shutting down system beyond operating hours (8-17)
#CUR_HOUR=$(date "+%H")
#if [ ${CUR_HOUR#0} -ge 17 ] || [ ${CUR_HOUR#0} -ge 0 -a ${CUR_HOUR#0} -le 8 ];
#then
#    echo "Outside operation hours" >> $CACHE_NODE_SCRIPT_LOG; 
#    echo "Shutting down now" >> $CACHE_NODE_SCRIPT_LOG;
#    sudo shutdown -h now
#fi;


if [ "$DETECT_I2C_HWCLK" != "UU" ];
then
    echo "Setting up HW Clock..." >> $CACHE_NODE_SCRIPT_LOG
    sudo modprobe i2c-dev;
    sudo su -c  'echo "ds1307 0x68" > /sys/class/i2c-adapter/i2c-1/new_device';
    sudo hwclock -s;
else
    echo "HW Clock detected." >> $CACHE_NODE_SCRIPT_LOG;
fi;

sudo hwclock -r

# Set the HCI Config to PSCAN so that other devices can connect to it
echo "Configuring Bluetooth adapter..."  >> $CACHE_NODE_SCRIPT_LOG;
sudo /bin/hciconfig hci1 down
sudo /bin/hciconfig hci0 down
sudo /bin/hciconfig hci0 up
sudo /bin/hciconfig hci0 piscan
echo "Done."  >> $CACHE_NODE_SCRIPT_LOG;

echo "Powering off HDMI..."  >> $CACHE_NODE_SCRIPT_LOG;
# /usr/bin/tvservice -o
echo "Done." >> $CACHE_NODE_SCRIPT_LOG;

# Run the main program
for i in {0..1000};
do
    echo "Script started."  >> $CACHE_NODE_SCRIPT_LOG;

    # WIFI_MODE=$(gpio read 4)
    # if [ $WIFI_MODE -eq 0 ];
    # then
    ACTIVE_SERVERS=$(ps u -C python3 | grep flask)
    if [ "$ACTIVE_SERVERS" = "" ];
    then
        export FLASK_APP=server.py
        export FLASK_DEBUG=1
        export LC_ALL=C.UTF-8
        export LANG=C.UTF-8
        sudo -E /usr/bin/python3 -m flask run --host=0.0.0.0 &
    fi;

    sudo /usr/bin/python3 main.py
    RES_CODE=$(echo $?)
    echo "Result = $RES_CODE"  >> $CACHE_NODE_SCRIPT_LOG;

    if [ $RES_CODE -eq $EXIT_RELOAD ];
    then
        echo "Script finished. " >> $CACHE_NODE_SCRIPT_LOG;
        echo "Reloading script..." >> $CACHE_NODE_SCRIPT_LOG;
        continue;
    fi;

    echo "Script finished. "  >> $CACHE_NODE_SCRIPT_LOG;
    break;

done;

if [ $RES_CODE -eq $EXIT_REBOOT ];
then
    echo "Rebooting now"  >> $CACHE_NODE_SCRIPT_LOG;
    sudo reboot
elif [ $RES_CODE -eq $EXIT_POWEROFF ];
then
    echo "Shutting down now" >> $CACHE_NODE_SCRIPT_LOG;
    sudo shutdown -h now
fi;

