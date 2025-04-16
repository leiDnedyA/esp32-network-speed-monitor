# ESP32 Network Speed Monitor

On its own, a device with a single network card (e.g a laptop) has **no way of knowing** what 
the current **upload and download speeds** are of the known wifi networks within its range are.
It can detect the 
[signal strength of wifi networks](https://techgrid.com/blog/wifi-signal-strength)
and the router's advertised maximum internet speed and switch to the fastest available 
networking accordingly, but this doesn't tell the whole story. This slow speed often leaves 
users looking something like this (especially on university campuses with 5 different wifi network options + hot spots):

![](./assets/sad_broken_computer_800_wht.jpg)

Our solution is to add a **second network card** into the equation via an ESP32! Using the 
second device, we can offload the task of switching between available networks, testing their 
current internet speeds, and keeping track of the fastest one. Any time a new network becomes 
the fastest one avilable, the ESP32 will send a message to the host machine letting it know 
to switch, the switch will happen seemlessly, and you don't have to worry about manually 
checking the other networks in your area to figure out which one is fastest.

![](./assets/happy-computer.jpg)

## Quick Start
Currently, the host PC script only runs on Linux distros that use
[Network Manager](https://networkmanager.dev/), which 
I'm pretty sure is all of them. For this tutorial, I'll only be going through how to run the 
script on Ubuntu:

### Prereqs
First, install `python3` and the `pyserial` library. Since the script must be run with 
root permissions, you should install `pyserial` as a system package rather than 
using a python package manager like pip.
```bash
# you probably already have python3, but just in case
sudo apt-get install python3 python3-serial 
```

Next, make sure that you have the Arduino IDE installed. 
[Here is the official guide for installing it on Ubuntu.](https://docs.arduino.cc/software/ide-v1/tutorials/Linux/) 
You can run it with the [Arduino CLI](https://github.com/arduino/arduino-cli) as well, 
but this guide assumes you're using the IDE.

### Run the Code
Here are the steps to run the speed monitor:
1. Plug the ESP32 into one of the USB ports on your machine.
2. Build the ESP32 C++ program with the Arduino IDE and load it onto the device.
3. From the root directory of this project, run the Python client using 
   the following command: 
    ```bash
    sudo ./python-client/main.py
    ```
4. Let it run in the background, and go about your life knowning that you're on the fastest 
   network available to your device :)

## Limitations & Future Features
Currently, this tool is just a prototype, and doesn't support every edge case. Here are a list 
of new functionalities that we would like to add:
1. Support for Windows and Mac
2. Support for WPA Enterprise Networks
3. Support for networks with non-ascii characters in their names
4. Ability to run multiple ESP32s in parallel to distribute the task of speed checking
5. A daemon wrapper around the script to run it in the background on boot
