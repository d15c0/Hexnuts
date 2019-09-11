#!/usr/bin/python

# 02/12/2018 - NOTES

# disabled BT scanning as it was being shitty
# Json logging will cause a exception if no 200 ok responce is given from endpoint
# gps lat long needs to be a value, if no GPS location can be found, then have exception but still send data

from logging.handlers import RotatingFileHandler
import threading
import argparse
import sys
import signal
from gps import *
import bluetooth
import manuf
from scapy.all import *
conf.verb = 0
import datetime
import logging
import collections
import requests
import base64
import json
from os import system, path, getuid, uname
from multiprocessing import Process

PROBE_REQUEST_TYPE=0
PROBE_REQUEST_SUBTYPE=4
AP_BROADCAST_SUBTYPE=8
RUN_PROGRAM=True

accessPoints = []
macAP = []

clients = []
btclients = []
macClient = []
uni = 0

Numclients = 0
Numap = 0
Currentloc = 0

NAME = 'Peanuts'
DESCRIPTION = "A New Version of Snoopy-NG, a command line tool for logging 802.11 probe request frames"
whmp = manuf.MacParser()

gpsd = None #seting the global variable

# Console colors
W  = '\033[0m'  # white (normal)
R  = '\033[31m' # red
G  = '\033[32m' # green
O  = '\033[33m' # orange<
B  = '\033[34m' # blue
P  = '\033[35m' # purple
C  = '\033[36m' # cyan
GR = '\033[37m' # gray
T  = '\033[93m' # tan

class GpsPoller(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        global gpsd #bring it in scope
        gpsd = gps(mode=WATCH_ENABLE) #starting the stream of info
        self.current_value = None
        self.running = True #setting the thread running to true
     
    def run(self):
        global gpsd
        while gpsp.running:
            try:
                if gpsd.waiting(): #only True if data is available
                    gpsd.next()
            except:
                print "GPSD Failed:"
                gpsd.close()
                sys.exit()

def signal_handler(signum, frame):        
    	global RUN_PROGRAM
        print "Detected Control-C"
	RUN_PROGRAM = False

def channel_hopper(interface):
    channels2g = [1,3,5,7,9,11,2,4,6,8,10,12,13,14]
    channels5g = [36,38,40,42,44,46,48,50,52,54,56,58,60,62,64,68,96,100,102,104,106,108,110,112,114,116,118,120,122,124,126,128,132,134,136,138,140,142,144,149,151,153,155,157,159,161,165]
    channelslimited = [1,6,11]

    channelsToScan = channels2g
    if args.fiveg:
 	channelsToScan = channels2g + channels5g    

    while True:
        try:
            #channel = random.randrange(1,12)
            #os.system("iw dev %s set channel %d" % (interface, channel))
            #time.sleep(1)
	    for chan in channelsToScan:
		os.system("iw dev %s set channel %d" % (interface, chan))
		time.sleep(2)
        except KeyboardInterrupt:
            break

def LoggingOfData(output):
    # setup our rotating logger
    if os.path.isfile(output) == False:
        f = open(output,'w')
        f.write('Time, Device, MAC Address, Manufacture, SSID, Crypto, Latitude, Longitude, Location, RSSI\n')
        f.close()
    global logger 
    logger = logging.getLogger(NAME)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(output, maxBytes=10000000, backupCount=99999)
    logger.addHandler(handler)

def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)

    parser.add_argument('-i', '--interface', help="capture interface")
    parser.add_argument('-o', '--output', default='out.log', help="logging output location")
    parser.add_argument('-d', '--delimiter', default=',', help="output field delimiter")
    parser.add_argument('-g', '--gpstrack', default=False, help="Enable/Disable GPS Tracking")
    parser.add_argument('-l', '--location', default='None', help="Location of survey")
    parser.add_argument('-a', '--access', default=False, help="Include AP's into the survey")
    parser.add_argument('-m', '--maps', default='', help="Send Map data to JSON endpoint")
    parser.add_argument('-b', '--bt', default=False, help="Scans BT Devices too (will need a BT dongle)")
    parser.add_argument('-5', '--fiveg', default=False, help="Include channels in the 5ghz range")

    return parser.parse_args()

def CryptoInfo(pkt):
    p = pkt[Dot11Elt]
    cap = pkt.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}"
                      "{Dot11ProbeResp:%Dot11ProbeResp.cap%}").split('+')
    crypto = ""
    while isinstance(p, Dot11Elt):
        if p.ID == 48:
            crypto = "WPA2"
        elif p.ID == 221 and p.info.startswith('\x00P\xf2\x01\x01\x00'):
            crypto = "WPA"
        p = p.payload
    if not crypto:
        if 'privacy' in cap:
            crypto = "WEP"
        else:
            crypto = "OPN"
    if "0050f204104a000110104400010210" in str(pkt).encode("hex"):
        crypto = crypto + R + " WPS"

    return crypto

def GetChannel(pkt):    
    p = pkt[Dot11Elt]
    
    #cap = pkt.sprintf("{Dot11Beacon:%Dot11Beacon.cap%}"
     #                 "{Dot11ProbeResp:%Dot11ProbeResp.cap%}").split('+')
    channel = ""
    while isinstance(p, Dot11Elt):	
        if p.ID == 3:            
            channel = ord(p.info)
	p = p.payload
        
    return channel

def getmac(intf):
    mac_addr = open('/sys/class/net/%s/address' % intf).read().rstrip()
    return mac_addr

def PacketHandler(pkt):
    global intf
    mymac = getmac(intf)
    noise = {
        'ff:ff:ff:ff:ff:ff',      # broadcast
        '00:00:00:00:00:00',      # broadcast
        '33:33:00:',              # ipv6 multicast
        '33:33:ff:',              # spanning tree
        '01:80:c2:00:00:00',      # multicast
        '01:00:5e:',			# broadcast
        'None',
        mymac              
    }

    if pkt.haslayer(Dot11):
        if pkt.addr2 not in noise:
            if pkt.type == PROBE_REQUEST_TYPE and pkt.subtype == PROBE_REQUEST_SUBTYPE:
                PrintPacketClient(pkt)
        if args.access:
            if pkt.type == PROBE_REQUEST_TYPE and pkt.subtype == AP_BROADCAST_SUBTYPE:
                PrintPacketAP(pkt)
       # if pkt.addr1 and pkt.addr2:
        #    PrintClientAP(pkt)
    if args.bt:
        try:
            btscanning()
        except Exception, e:
            print 'Caught exception while running BT Sniffing',e

def PrintClientAP(pkt):
    global intf
    mymac = getmac(intf)
    noise = {
        'ff:ff:ff:ff:ff:ff',      # broadcast
        '00:00:00:00:00:00',      # broadcast
        '33:33:00:',              # ipv6 multicast
        '33:33:ff:',              # spanning tree
        '01:80:c2:00:00:00',      # multicast
        '01:00:5e:',            # broadcast
        'None',
        mymac              
    }

    if pkt.addr2 in macAP:
        if pkt.addr1 not in noise:
            if pkt.type in [1, 2]:
                print "Client: " + pkt.addr1.upper() + " -> " + pkt.addr2

def PrintPacketAP(pkt):
    global Numap, Currentloc
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

    ssid_probe = pkt.info
    manufacture = str(whmp.get_manuf(pkt.addr2))
    mac = pkt.addr2

    crypto = CryptoInfo(pkt)
    rssival = str(get_rssi(pkt.notdecoded))
    channel = str(GetChannel(pkt))

    if args.gpstrack:
        gpslat = str(gpsd.fix.latitude)
        gpslong = str(gpsd.fix.longitude)
        gpstime = str(gpsd.fix.time)
    else:
        gpslat = "nil"
        gpslong = "nil"
        gpstime = "nil"

    # Logging info
    fields = []
    fields.append(st) # Log Time
    fields.append('AP') # Log Client or AP
    fields.append(mac) # Log Mac Address
    fields.append(manufacture) # Log Device Manufacture
    fields.append(ssid_probe) # Log SSID
    fields.append(crypto) # Log Crypto
    fields.append(gpslat) # Log GPS data
    fields.append(gpslong) # Log GPS data
    fields.append(args.location) # Log Location data
    fields.append(rssival) # RSSI
    
    # if AP ssid is not in clients and its not empty then print out, add  AP ssid and mac to lists
    if ssid_probe not in accessPoints and ssid_probe != "":
        accessPoints.append(ssid_probe)
        macAP.append(mac)
        print W+ '[' +R+ 'AP' +W+ ':' +C+ manufacture +W+ '/' +B+ mac +W+ '] [' +T+ crypto +W+ '] [' +G+ 'SSID' +W+ ': ' +O+ ssid_probe.decode("utf-8") +W+ '] [' +P+ 'RSSI' +W+ ':' +T+ rssival +W+ '] [' +P+ 'Channel' +W+ ':' +T+ channel +W+ ']'
        Numap += 1
    # if ssid is in clients but mac isnt seen before then print out and add the mac to the list
    elif ssid_probe in accessPoints and mac not in macAP:
        macAP.append(mac)
        print W+ '[' +R+ 'AP' +W+ ':' +C+ manufacture +W+ '/' +B+ mac +W+ '] [' +T+ crypto +W+ '] [' +G+ 'SSID' +W+ ': ' +O+ ssid_probe.decode("utf-8") +W+ '] [' +P+ 'RSSI' +W+ ':' +T+ rssival +W+ '] [' +P+ 'Channel' +W+ ':' +T+ channel +W+ ']'
        Numap += 1
    
    logger.info(args.delimiter.join(fields))

    if args.maps:
        # MAPPING SYSTEM
        jsondata = {"devicetype": "stupie", "time": st, "channel": channel,  "gpstime": gpstime, "device": "AP", "macaddress": mac, "manuf": manufacture, "ssid": ssid_probe, "crypto": crypto, "longlat": [gpslong, gpslat], "location": args.location, "rssi": rssival}
        data_json = json.dumps(jsondata)

        s = requests.Session()
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        s.post(args.maps, data=data_json, headers=headers)
        
        # MAPPING SYSTEM


def PrintPacketClient(pkt):    
    global Numclients, Currentloc
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

    ssid_probe = pkt.getlayer(Dot11ProbeReq).info
    manufacture = str(whmp.get_manuf(pkt.addr2))
    mac = pkt.addr2
    crypto = 'None' #instead of being blank, client has none for crypto probe request
    rssival = str(get_rssi(pkt.notdecoded))
    channel = str(GetChannel(pkt))

    if args.gpstrack:
        gpslat = str(gpsd.fix.latitude)
        gpslong = str(gpsd.fix.longitude)
        gpstime = str(gpsd.fix.time)
    else:
        gpslat = "nil"
        gpslong = "nil"
        gpstime = "nil"

    # Logging info
    fields = []
    fields.append(st) # Log Time
    fields.append('Client') # Log Client or AP
    fields.append(mac) # Log Mac Address
    fields.append(manufacture) # Log Device Manufacture
    fields.append(ssid_probe) # Log SSID
    fields.append(crypto) # Log Crypto
    fields.append(gpslat) # Log GPS data
    fields.append(gpslong) # Log GPS data
    fields.append(args.location) # Log Location data
    fields.append(rssival) # RSSI
    
    # if ssid is not in clients and its not empty then print out, add ssid and mac to lists
    if ssid_probe not in clients and ssid_probe != "":
        clients.append(ssid_probe)
        macClient.append(mac)
        print W+ '[' +R+ 'Client' +W+ ':' +C+ manufacture +W+ '/' +B+ mac +W+ '] [' +G+ 'SSID' +W+ ': ' +O+ ssid_probe.decode("utf-8") +W+ '] [' +P+ 'RSSI' +W+ ':' +T+ rssival +W+ '] [' +P+ 'Channel' +W+ ':' +T+ channel +W+ ']' 
    # if ssid is in clients but mac isnt seen before then print out and add the mac to the list
    elif ssid_probe in clients and mac not in macClient:
        macClient.append(mac)
        print W+ '[' +R+ 'Client' +W+ ':' +C+ manufacture +W+ '/' +B+ mac +W+ '] [' +G+ 'SSID' +W+ ': ' +O+ ssid_probe.decode("utf-8") +W+ '] [' +P+ 'RSSI' +W+ ':' +T+ rssival +W+ '] [' +P+ 'Channel' +W+ ':' +T+ channel +W+ ']'
        Numclients += 1
    # if mac is not in the list and the probe has a broadcast (empty) then add mac to list
    elif mac not in macClient and ssid_probe == "":
        macClient.append(mac)
        print W+ '[' +R+ 'Client' +W+ ':' +C+ manufacture +W+ '/' +B+ mac +W+ '] [' +GR+ '*New Client*' +W+ '] [' +P+ 'RSSI' +W+ ':' +T+ rssival +W+ '] [' +P+ 'Channel' +W+ ':' +T+ channel +W+ ']'
        Numclients += 1

    logger.info(args.delimiter.join(fields))

    if args.maps:
        # MAPPING SYSTEM
        jsondata = {"devicetype": "stupie", "time": st, "channel": channel, "gpstime": gpstime, "device": "CLIENT", "macaddress": mac, "manuf": manufacture, "ssid": ssid_probe, "crypto": "N/A", "longlat": [gpslong, gpslat], "location": args.location, "rssi": rssival}
        data_json = json.dumps(jsondata)

        s = requests.Session()
        headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
        s.post(args.maps, data=data_json, headers=headers)
        # MAPPING SYSTEM
        

def get_rssi(extra):
    rssi = int(-(256 - ord(extra[-2:-1])));
    if rssi not in xrange(-100, 0):
        rssi = (-(256 - ord(extra[-4:-3])));
    if rssi < -100:
        return -1;
    return rssi;


def getWirelessInterfacesList():
    networkInterfaces=[]        
    command = ["iwconfig"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.wait()
    (stdoutdata, stderrdata) = process.communicate();
    output = stdoutdata
    lines = output.splitlines()
    for line in lines:
            if(line.find("IEEE 802.11")!=-1):
                    networkInterfaces.append(line.split()[0])
    return networkInterfaces

def startup_checks():
    if getuid() != 0:
        print R + "User is not Root."
        sys.exit()

    if uname()[0].startswith("Linux") and not "Darwin" not in uname():
        print R + "Wrong OS."
        sys.exit()
	return;

def logo():
    print O + '''
    %s______                      _       
    | ___ \                    | |      
    | |_/ /__  __ _ _ __  _   _| |_ ___ 
    |  __/ _ \/ _` | '_ \| | | | __/ __|
    | | |  __/ (_| | | | | |_| | |_\__ \

    \_|  \___|\__,_|_| |_|\__,_|\__|___/
    %s
    %sRelease Date%s: 01/12/2018
    %sRelease Version%s: V.2.0
    %sCode%s: stuart@sensepost.com // @NoobieDog
    %sVisit%s:  www.sensepost.com // @sensepost
    ''' %(B,C,R,W,R,W,R,W,R,W)         
    print '['+G+'*'+W+'] Wifi Probe Investigator'
    print '['+G+'-----------------------------------------------------'+W+']'

def main(intf):
    global RUN_PROGRAM
    p = Process(target = channel_hopper, args=(intf,))
    p.start()

    while RUN_PROGRAM:
    	try:	
        	sniff(iface=intf, prn=PacketHandler, store=0)
    	except Exception, e:
        	print 'Caught exception while running sniff()',e
		time.sleep(2)
        

    p.terminate()
    sys.exit()

def btscanning():
    devices = bluetooth.discover_devices(duration=1, lookup_names = True)

    for addr, name in devices:
        if addr not in btclients:
            print W+ '[' +R+ 'Bluetooth Client' +W+ ':' +B+ addr +W+ '] [' +G+ 'Name' +W+ ': ' +O+ name +W+ ']'
            btclients.append(addr)

if __name__=="__main__":
    signal.signal(signal.SIGINT,signal_handler)
    args = parse_args()
    
    start = time.time()

    startup_checks()

    LoggingOfData(args.output)

    if not args.interface:
        intf = raw_input('['+G+'*'+W+'] Enter the Name of the interface to sniff: ')
        print ("\n")
    else:
        intf = args.interface

    if "mon" not in intf: # yes i know this doesnt work with ubuntu/mint at the mo...
        print '['+G+'*'+W+'] Setting Wireless card into Monitor Mode'
        if 'mon' not in getWirelessInterfacesList():
            #call(['airmon-ng', 'check', 'kill'], stdout=DN, stderr=DN)
            cmd = ['airmon-ng', 'start' ,intf]
            p = subprocess.Popen(cmd)
            p.wait()
        intf = intf + 'mon'

    os.system('clear')

    logo()

    if args.gpstrack:
        try:    
            gpsp = GpsPoller() # create the thread
        except Exception, e:
            print 'Caught exception while running GPS',e

        try:
            gpsp.start() # start it up
        except Exception, e:
            print 'Caught exception while running GPS',e
            gpsp.running = False
            gpsp.join() # wait for the thread to finish what it's doing
            sys.exit()
    try:
        main(intf)
    except (KeyboardInterrupt, SystemExit):
        raise


# Finish off with Tidy up of CSV. 

print '\n \033[31m%d \033[0mClients | \033[33m%d \033[0mAPs' % (Numclients, Numap)

outfile = args.output + '.csv'

print G + '\n Creating CSV' +W+ ': ' + outfile
try:
    with open(args.output, 'rb') as inf, open(outfile, 'wb') as outf:
        outf.writelines(collections.OrderedDict.fromkeys(inf))
except Exception, e:
            print R + 'Caught exception while creating CSV File',e

# Print Program Time

print G + '\n Elapsed Time' +W+ ': %s' % (time.time() - start)
