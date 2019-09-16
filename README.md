Hexnuts V1.0 (modified version of Peanuts by Noobiedog)                                  
                                    
========

**** FOR EDUCATIONAL USE! Use at your own risk. **** <br />

+ Tested on: Linux 3.2.6 Ubuntu/Debian (Kali)/Rpi<br />

## Installation:

### Dependencies:

#### Required:

- Python 2.7+
- Scapy / python-gps / python-bluez
- aircrack-ng

#### Installing from Download

```bash
pip install argparse datetime gps scapy logging requests
apt-get install python-gps bluetooth bluez python-bluez
```

#### To start GPS in kali/Ubuntu (in a separate terminal window)

```bash
service gps start
gpsd -D 5 -N -n /dev/ttyUSB0
```
##  Sample commands

#### Simple

``` bash
python peanuts.py -i wlan0 -l Home -o Capture1.csv
```

-i Interface (Doesnt matter if not in monitor mode, the program will do it)<br />
-l location or OP name, whatever you want to identify this capture<br />
-o Output file name for the CSV<br />

#### Advanced

``` bash
python hexnuts.py -i wlan0mon -l target1 -o unknown.csv -a true -m http://localhost:8080/api/data -g true

```

-i Interface (Doesn't matter if not in monitor mode, the program will do it)<br />
-l location or OP name, whatever you want to identify this capture<br />
-a Include Access Points too in the results<br />
-g Get GPS location of your device (Not tested with Nethunter, yet. Also will need GPSD running)<br />
-o Output file name for the CSV<br />
-b Start Bluetooth sniffing too<br /> (make sure you have either bt enabled in vm or  dongle)
-m Send Map data to JSON endpoint

## Lets See it in Action

[![ASCIICinema](http://i.imgur.com/saR06iC.png)](https://asciinema.org/a/4lf58gw5psnik38wb4umud5r0)

Happy Hacking

NOTE: This method of WIFI tracking is slowly dying with the new IOS 10 Updates and Android updates.

https://gist.github.com/computerality/3e0bc104cd216bf0f03f8d3aa8fbf081 line 176
