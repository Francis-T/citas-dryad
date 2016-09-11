# updating & upgrading aptitude repositories
echo "Updating repositories"
sudo apt-get update
echo "Upgrading repositories" 
sudo apt-get upgrade

# retrieving and installing bluez
echo "Retrieving and installation of bluez"
cd ~
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.41.tar.xz
tar xvf bluez-5.41.tar.xz

cd bluez-5.41
sudo apt-get install -y libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev
./configure

make
sudo make install

# Enabling bluez service to automatically start upon system boot
echo "Enabling bluetooth service"
sudo systemctl enable bluetooth

# adding --experimental in /lib/systemd/system/bluetooth.service ExecStart
echo "Configuring bluetooth service for ble"
echo "%s/bluetoothd /bluetoothd --experimental/g
w
q
" | ex /lib/systemd/system/bluetooth.service

echo "Reloading of daemon and restarting bluetooth service"
sudo systemctl daemon-reload
sudo systemctl restart bluetooth

# dependencies and installation for pybluez ble
sudo apt-get install pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0 dev python-dev
pip install pybluez[ble]

# install sqlite3
sudo apt-get install sqlite3

# creation and activation of virtual environment with default python interpreter of python3.4
virtualenv -p /usr/bin/python3.4 venv
. venv/bin/activate

# installation of required python modules
pip install -r requirements.txt


