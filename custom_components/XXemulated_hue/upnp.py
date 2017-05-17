"""Provides a UPNP discovery method that mimicks Hue hubs."""
import threading
import socket
import logging
import os
import select
import random
import time

from aiohttp import web

from homeassistant import core
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)


class DescriptionXmlView(HomeAssistantView):
    """Handles requests for the description.xml file."""

    url = '/description.xml'
    name = 'description:xml'
    requires_auth = False

    def __init__(self, config):
        """Initialize the instance of the view."""
        self.config = config

    @core.callback
    def get(self, request):
        """Handle a GET request."""
        xml_template = """<?xml version="1.0" encoding="UTF-8" ?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
<specVersion>
<major>1</major>
<minor>0</minor>
</specVersion>
<URLBase>http://{0}:{1}/</URLBase>
<device>
<deviceType>urn:schemas-upnp-org:device:Basic:1</deviceType>
<friendlyName>HASS Bridge ({0})</friendlyName>
<manufacturer>Royal Philips Electronics</manufacturer>
<manufacturerURL>http://www.philips.com</manufacturerURL>
<modelDescription>Philips hue Personal Wireless Lighting</modelDescription>
<modelName>Philips hue bridge 2015</modelName>
<modelNumber>BSB002</modelNumber>
<modelURL>http://www.meethue.com</modelURL>
<serialNumber>{1}</serialNumber>
<UDN>uuid:2f402f80-da50-11e1-{1}-001788255acc</UDN>
</device>
</root>
"""

        resp_text = xml_template.format(
            self.config.advertise_ip, self.config.advertise_port)

        return web.Response(text=resp_text, content_type='text/xml')


class UPNPResponderThread(threading.Thread):
    """Handle responding to UPNP/SSDP discovery requests."""

    _interrupted = False

    def __init__(self, host_ip_addr, listen_port, upnp_bind_multicast,
                 advertise_ip, advertise_port, target_ip):
        """Initialize the class."""
        threading.Thread.__init__(self)

        self.host_ip_addr = host_ip_addr
        self.listen_port = listen_port
        self.upnp_bind_multicast = upnp_bind_multicast
        self.advertise_ip = advertise_ip
        self.advertise_port = advertise_port
        self.target_ip = target_ip

        # Set up a pipe for signaling to the receiver that it's time to
        # shutdown. Essentially, we place the SSDP socket into nonblocking
        # mode and use select() to wait for data to arrive on either the SSDP
        # socket or the pipe. If data arrives on either one, select() returns
        # and tells us which filenos have data ready to read.
        #
        # When we want to stop the responder, we write data to the pipe, which
        # causes the select() to return and indicate that said pipe has data
        # ready to be read, which indicates to us that the responder needs to
        # be shutdown.
        self._interrupted_read_pipe, self._interrupted_write_pipe = os.pipe()

    def send_adv(self, addr, data):
        # Note that the double newline at the end of
        # this string is required per the SSDP spec
        resp_template = """HTTP/1.1 200 OK
CACHE-CONTROL: max-age=60
EXT:
LOCATION: http://{0}:{1}/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/0.1
hue-bridgeid: {1}
ST: urn:schemas-upnp-org:device:basic:1
USN: uuid:Socket-1_0-221438K0100073::urn:schemas-upnp-org:device:basic:1

"""
        if self.target_ip is not None:
            if addr[0] != self.target_ip:
                return

        # Randomize the mcast response - otherwise Echo can lose messages
        r = random.randint(1, 8)
        time.sleep(r)

        upnp_response = resp_template.format(
            self.advertise_ip, self.advertise_port).replace("\n", "\r\n") \
                                         .encode('utf-8')
        resp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        resp_socket.sendto(upnp_response, addr)
        resp_socket.close()

    def run(self):
        """Run the server."""
        # Listen for UDP port 1900 packets sent to SSDP multicast address
        ssdp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ssdp_socket.setblocking(False)

        # Required for receiving multicast
        ssdp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ssdp_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(self.host_ip_addr))

        ssdp_socket.setsockopt(
            socket.SOL_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton("239.255.255.250") +
            socket.inet_aton(self.host_ip_addr))

        if self.upnp_bind_multicast:
            ssdp_socket.bind(("239.255.255.250", 1900))
        else:
            ssdp_socket.bind((self.host_ip_addr, 1900))

        while True:
            if self._interrupted:
                clean_socket_close(ssdp_socket)
                return

            try:
                read, _, _ = select.select(
                    [self._interrupted_read_pipe, ssdp_socket], [],
                    [ssdp_socket])

                if self._interrupted_read_pipe in read:
                    # Implies self._interrupted is True
                    clean_socket_close(ssdp_socket)
                    return
                elif ssdp_socket in read:
                    data, addr = ssdp_socket.recvfrom(1024)
                else:
                    continue
            except socket.error as ex:
                if self._interrupted:
                    clean_socket_close(ssdp_socket)
                    return

                _LOGGER.error("UPNP Responder socket exception occured: %s",
                              ex.__str__)

            if "M-SEARCH" in data.decode('utf-8'):
                # SSDP M-SEARCH method received, respond to it with our info
                self.send_adv(addr, data)

    def stop(self):
        """Stop the server."""
        # Request for server
        self._interrupted = True
        os.write(self._interrupted_write_pipe, bytes([0]))
        self.join()


def clean_socket_close(sock):
    """Close a socket connection and logs its closure."""
    _LOGGER.info("UPNP responder shutting down.")

    sock.close()
