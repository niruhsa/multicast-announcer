#!/usr/bin/python3
import socket, time, ipaddress, netifaces, string, random, sys, logging
from netaddr import IPAddress, IPNetwork

class MulticastAnnouncerClient:

    def __init__(self, **kwargs):
        self.MCAST_GROUP = '224.1.1.1'
        self.MCAST_PORT = 4180
        self.MCAST_TTL = 3
        self.blacklisted_interfaces = [ 'lo', 'lo0' ]
        self.name = kwargs['nickname']
        self.ipv6 = kwargs['ipv6']
        self.timer = kwargs['timer']
        self.verbose = kwargs['v']
        self.ips = {}
        self.last_transmitted = 0
        self.blacklist = str(kwargs['bc']).split(",")
        self.blacklisted_subnets = []

        self.log = logging.getLogger(__name__)
        syslog = logging.StreamHandler()

        formatter = logging.Formatter("%(message)s")
        syslog.setFormatter(formatter)
        self.log.setLevel(logging.DEBUG)
        self.log.addHandler(syslog)
        self.log = logging.LoggerAdapter(self.log, { 'app_name': 'muCast' })

        if self.name is None or len(self.name) == 0: raise Error("The name that you entered cannot be empty")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.MCAST_TTL)

        self.blacklistedSubnets()
        self.listenForChanges()

    def listenForChanges(self):
        while True:
            try:
                old_ips = self.ips.copy()
                self.getIPs()
                for interface in self.ips.keys():
                    for ip in self.ips[interface]:
                        if interface not in old_ips.keys(): self.sendPacket(ip['addr'])
                        else:
                            match = False
                            for oip in old_ips[interface]:
                                if oip['addr'] == ip['addr']: match = True
                            if not match: self.sendPacket(ip['addr'])

                if time.time() - self.last_transmitted > int(self.timer):
                    for interface in self.ips:
                        for ip in self.ips[interface]:
                            self.sendPacket(ip['addr'])
            except Exception as e:
                if self.verbose: self.log.error("[CLIENT - listenForChanges()]: {}".format(e))
                else: pass
            time.sleep(1)

    def blacklistedSubnets(self):
        for subnet in self.blacklist:
            try: self.blacklisted_subnets.append(IPNetwork(str(subnet)))
            except: pass

    def getIPs(self):
        for inter in netifaces.interfaces():
            if inter not in self.blacklisted_interfaces:
                interface = netifaces.ifaddresses(inter)
                for address in interface:
                    if inter not in self.ips: self.ips[inter] = interface[address]
                    else: self.ips[inter] += interface[address]

                    l = self.ips[inter].copy()
                    new_l = []
                    for item in l:
                        in_new = False
                        for oitem in new_l:
                            if item['addr'] == oitem['addr']: in_new = True
                        if not in_new: new_l.append(item)
                    self.ips[inter] = new_l
    
    def sendPacket(self, address):
        try:
            is_blacklisted = False
            for b_subnet in self.blacklisted_subnets:
                if IPAddress(str(address)) in b_subnet: is_blacklisted = True
            
            if not is_blacklisted:
                id = self.randomString()
                t = time.time()
                data = "{}:{}:{}:{}".format(self.name, address, id, t)
                ip_type = ipaddress.ip_address(address)
                if self.verbose or (self.verbose and isinstance(ip_type, ipaddress.IPv6Address) and self.ipv6):
                    self.log.info("[VERBOSE] Sending packet {} at {} with content {}".format(id, t, self.name + ":" + address))
                
                if isinstance(ip_type, ipaddress.IPv6Address) and self.ipv6: self.sock.sendto(bytes(data, "utf-8"), (self.MCAST_GROUP, self.MCAST_PORT))
                else: self.sock.sendto(bytes(data, "utf-8"), (self.MCAST_GROUP, self.MCAST_PORT))
                
                self.last_transmitted = t

            return True
        except Exception as e:
            if self.verbose and "failed to detect" not in str(e) and "_version" not in str(e):
                self.log.error("[CLIENT - sendPacket()]: {}".format(e))
            return False

            

    def randomString(self, length=8):
        ret = ""
        chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
        for i in range(length): ret += chars[random.randint(0, len(chars) - 1)]
        return ret
