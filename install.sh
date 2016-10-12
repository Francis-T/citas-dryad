# updating & upgrading aptitude repositories
echo "Updating repositories"
sudo apt-get update 
#&& sudo apt-get -y upgrade

# retrieving and installing bluez
echo "Retrieving and installation of bluez"
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.41.tar.xz
tar xvf bluez-5.41.tar.xz

cd bluez-5.41
sudo apt-get install -y libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev
./configure

make
sudo make install
cd ..

# Enabling bluez service to automatically start upon system boot
echo "Enabling bluetooth service"
sudo systemctl enable bluetooth

# adding --experimental in /lib/systemd/system/bluetooth.service ExecStart for ble
echo "Configuring bluetooth service for ble"
sudo sed -i -e 's/bluetooth\/bluetoothd/bluetooth\/bluetoothd --experimental/g' /lib/systemd/system/bluetooth.service

echo "Reloading of daemon, restarting bluetooth service, and resetting of hci0"
sudo systemctl daemon-reload
sudo systemctl restart bluetooth
sudo hciconfig hci0 reset

# dependencies and installation for pybluez ble
echo "Installing dependencies and pybluez ble"
sudo apt-get -y install python-dev pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0-dev

# install sqlite3
echo "Installing sqlite3"
sudo apt-get install sqlite3

# creation and activation of virtual environment with default python interpreter of python3.4
sudo pip install virtualenv
virtualenv -p /usr/bin/python3.4 venv
. venv/bin/activate

# installation of required python modules
# pip install -r requirements.txt
pip install pybluez
pip install bluepy

