#!/bin/bash

#sleep 20

cd /home/pi/Programs/citas-dryad/

# Set the HCI Config to PSCAN so that other devices can connect to it
echo "Configuring Bluetooth adapter..."
sudo /bin/hciconfig hci1 down
sudo /bin/hciconfig hci0 down
sudo /bin/hciconfig hci0 up
sudo /bin/hciconfig hci0 piscan
echo "Done."


# Run the main program
echo "Running program..."
for i in {0..100};
do
    echo "Iteration $i started."
    sudo /usr/bin/python3 main-mt.py
	RES_CODE=$(echo $?)
    if [ $RES_CODE -ne 0 ];
    then
        break;
    fi;
    
    echo "Iteration $1 finished."
done;
echo "Program finished. "

