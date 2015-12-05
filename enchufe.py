# enchufe.py
# High-level socket API

import socket

class Address(object):
    """IPv4 Address and port"""
    def __init__(self, addr, port=None):
        """Args:
        - addr is a IPv4 or a host name string
        - port is an integer value between 0 and 65535

        As an alternative, you can use a sequence (tuple, list, ...) with the
        two values defined above and pass it as 'addr'
        """
        if port is None and len(addr) == 2:
            hostname = addr[0]
            port = addr[1]
        elif port is not None:
            hostname = addr
        else:
            raise TypeError("Unsupported addr: {}".format(addr))

        ip = socket.gethostbyname(hostname)
        if ip != hostname:
            # hostname is not an IP address, store it
            super().__setattr__('hostname', hostname)

        # Check port range
        if not 0 <= port <= 0xFFFF:
            raise ValueError("Port out of range")

        super().__setattr__('tuple', (ip, port))

    def __repr__(self):
        return repr(self.tuple)

    def __str__(self):
        if 'hostname' in self.__dict__:
            addr = self.hostname
        else:
            addr = self.ip
        return '{}:{}'.format(addr, self.port)

    def __eq__(self, other):
        if isinstance(other, Address):
            return self.tuple == other.tuple
        else:
            return NotImplemented

    def __hash__(self):
        return hash((Address, self.tuple))

    def __getattr__(self, name):
        if name == 'ip':
            return self.tuple[0]

        if name == 'port':
            return self.tuple[1]

        if name == 'hostname':
            hostname = socket.gethostbyaddr(self.ip)[0]
            super().__setattr__('hostname', hostname)
            return hostname

        errmsg = "'Address' object has no attribute '{}'".format(name)
        raise AttributeError(errmsg)

    def __setattr__(self, name, value):
        self._error()

    def __delattr__(self, name):
        self._error()

    def __len__(self):
        return 2

    def __getitem__(self, key):
        return self.tuple[key]

    def _error(self):
        raise RuntimeError("Read-only class: Address")


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
            self.sock.send(datagram.payload)
        else:
            self.sock.sendto(datagram.payload, datagram.dst)

    def receive(self):
        dst = self.sock.getsockname()
        if self.connected:
            src = self.sock.getpeername()
            data = self.sock.recv(Datagram.MAXBYTES)
        else:
            data, src = self.sock.recvfrom(Datagram.MAXBYTES)
        return Datagram(data, src=src, dst=dst)
