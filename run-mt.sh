#!/bin/bash

CACHE_NODE_HOME=/home/pi/Programs/citas-dryad/

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
echo "Done."

cd $CACHE_NODE_HOME

# Set the HCI Config to PSCAN so that other devices can connect to it
echo "Configuring Bluetooth adapter..."
sudo /bin/hciconfig hci1 down
sudo /bin/hciconfig hci0 down
sudo /bin/hciconfig hci0 up
sudo /bin/hciconfig hci0 piscan
echo "Done."


# Run the main program
echo "Script started."
for i in {0..100};
do
    echo "Iteration $i started."
    sudo /usr/bin/python3 main-mt.py
	RES_CODE=$(echo $?)
    echo "Result = $RES_CODE"
    if [ $RES_CODE -ne 0 ];
    then
        break;
    fi;
    
    echo "Iteration $1 finished."
done;
echo "Script finished. "

# Shutdown the RPI as well if PWDN is received
if [ $RES_CODE -eq 2 ];
then
    echo "Shutting down now";
#    sudo shutdown -h now
fi;

