# updating aptitude repositories
sudo apt-get update

# retrieving and installing bluez
cd ~
wget http://www.kernel.org/pub/linux/bluetooth/bluez-5.41.tar.xz
tar xvf bluez-5.41.tar.xz

cd bluez-5.41
sudo apt-get install -y libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev
./configure

make
sudo make install
## EXTRA: sudo nano /lib/systemd/system/bluetooth.service and add --experimental on ExecStart

# dependencies and installation for pybluez ble
sudo apt-get install pkg-config libboost-python-dev libboost-thread-dev libbluetooth-dev libglib2.0 dev python-dev
pip install pybluez[ble]

# install sqlite3
sudo apt-get install sqlite3

