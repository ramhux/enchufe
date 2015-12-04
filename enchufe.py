# enchufe.py
# High-level socket API

import socket

class Datagram(object):
    """UDP Datagram

    Datagram attributes
    * payload: Binary data
    * src: Source (address, port) pair
    * dst: Destination (address, port) pair
    """

    MAXBYTES = 0xFFFF

    def __init__(self, *args, **kwargs):
        self.src = kwargs.pop('src', None)
        self.dst = kwargs.pop('dst', None)
        self.payload = bytes(*args, **kwargs)
        #FIXME check values

    def __repr__(self):
        r = 'Datagram({!r}'.format(self.payload)
        if self.src is not None:
            r += ', src={!r}'.format(self.src)
        if self.dst is not None:
            r += ', dst={!r}'.format(self.dst)
        r += ')'
        return r

    def __bytes__(self):
        return self.payload

    def __eq__(self, other):
        if isinstance(other, Datagram):
            if self.payload != other.payload:
                return False
            if self.src != other.src:
                return False
            if self.dst != other.dst:
                return False
            return True
        else:
            return NotImplemented

    # Mutable class, no hash
    #def __hash__(self):
    #    return hash((self.payload, self.src, self.dst))

    def __len__(self):
        return len(self.payload)

    def __getitem__(self, key):
        return self.payload[key]

    def response(self, data):
        datagram = Datagram(data, src=self.dst, dst=self.src)
        return datagram


class UDP(object):
    """Basic UDP socket"""

    def __init__(self, bind=None, connect=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if bind is not None:
            self.sock.bind(bind)
        if connect is not None:
            self.sock.connect(connect)
            self.connected = True
        else:
            self.connected = False

    def send(self, datagram):
        if self.connected:
            pass
        else:
            self.sock.sendto(datagram.payload, datagram.dst)

    def receive(self):
        if self.connected:
            datagram = Datagram()
        else:
            data, addr = self.sock.recvfrom(Datagram.MAXBYTES)
            datagram = Datagram(data, src=addr, dst=self.sock.getsockname())
        return datagram
