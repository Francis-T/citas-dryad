#!/bin/bash

# Set the HCI Config to PSCAN so that other devices can connect to it
echo "Configuring Bluetooth adapter..."
sudo hciconfig hci1 down
sudo hciconfig hci0 down
sudo hciconfig hci0 up
sudo hciconfig hci0 piscan
echo "Done."

#cd ~/Programs/python-projects/dryad-node/

# Run the main program
echo "Running program..."
for i in {0..100};
do
    echo "Iteration $i started."
    sudo venv3/bin/python main-mt.py;
    RES_CODE=$(echo $?)
    if [ $RES_CODE -ne 0 ];
    then
        break;
    fi;
    
    echo "Iteration $1 finished."
done;
echo "Program finished. "

