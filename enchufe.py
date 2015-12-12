# enchufe.py
# High-level socket API

import socket
import datetime

from datetime import datetime, timedelta

def _readonly_error(obj):
    msg = 'Read-only class: {}'.format(obj.__class__.__name__)
    raise RuntimeError(msg)

def _attribute_error(obj, name):
    msg = "'{}' object has no attribute '{}'"
    msg = msg.format(obj.__class__.__name__, name)
    raise AttributeError(msg)

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

        _attribute_error(self, name)

    def __setattr__(self, name, value):
        _readonly_error(self)

    def __delattr__(self, name):
        _readonly_error(self)

    def __len__(self):
        return len(self.tuple)

    def __getitem__(self, key):
        return self.tuple[key]


class Datagram(object):
    """UDP Datagram

    Datagram attributes
    * payload: Binary data
    * src: Source (address, port) pair
    * dst: Destination (address, port) pair
    """

    MAXBYTES = 0xFFFF

    def __init__(self, *args, **kwargs):
        src = kwargs.pop('src', None)
        dst = kwargs.pop('dst', None)

        src = None if src is None else Address(src)
        dst = None if dst is None else Address(dst)
        super().__setattr__('src', src)
        super().__setattr__('dst', dst)

        payload = bytes(*args, **kwargs)
        super().__setattr__('payload', payload)
        if not 0 <= len(self.payload) <= self.MAXBYTES:
            raise ValueError('Too much data, max size {}'.format(self.MAXBYTES))

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

    def __hash__(self):
        return hash((self.payload, self.src, self.dst))

    def __setattr__(self, name, value):
        _readonly_error(self)

    def __delattr__(self, name):
        _readonly_error(self)

    def __len__(self):
        return len(self.payload)

    def __getitem__(self, key):
        return self.payload[key]

    def response(self, *args, **kwargs):
        """Generates a new Datagram swapping src and dst"""
        kwargs['src'] = self.dst
        kwargs['dst'] = self.src
        return Datagram(*args, **kwargs)


class UDP(object):
    """Basic UDP socket

    UDP attributes:
    timeout -> Timeout for blocking operations
    local -> Local Address (ip, port)
    remote -> Remote Address (ip, port)
    """

    timeout = None

    def __init__(self, bind=None, connect=None, broadcast=False):
        """Create a basic UDP socket

        After the UDP socket is created:
        If bind is not None, bind to the address and port sequence.
        If connect is not None, connect to the address and port sequence.
        """
        self.connected = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if bind is not None:
            self.bind(bind)
        if connect is not None:
            self.connect(connect)
        if broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def __getattr__(self, name):
        if name == 'local':
            local = Address(self.sock.getsockname())
            if local.port != 0: #if bound, save it
                self.local = local
            return local

        if name == 'remote':
            if not self.connected:
                _attribute_error(self, name)
            remote = Address(self.sock.getpeername())
            self.remote = remote
            return remote

        _attribute_error(self, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def send(self, data):
        """Send data through UDP socket

        data -> a Datagram. Optionally binary data (bytes) if connected.
        """
        if hasattr(data, 'dst') and data.dst is not None:
            self.sock.sendto(bytes(data), tuple(data.dst))
        elif self.connected:
            self.sock.send(bytes(data))
        else:
            raise RuntimeError('No dst info to send data')

    def broadcast(self, data, port=None):
        """Send data to all computers in the network"""
        if port is None:
            port = data.dst.port
        data = Datagram(data, dst=('<broadcast>', port))
        self.send(data)

    def receive(self):
        """Receive data from the UDP socket

        Returns a Datagram or None if timeout was reached.
        """
        self.sock.settimeout(self.timeout)
        dst = self.local
        if self.connected:
            src = self.remote
            try:
                data = self.sock.recv(Datagram.MAXBYTES)
            except socket.timeout:
                return None
        else:
            try:
                data, src = self.sock.recvfrom(Datagram.MAXBYTES)
            except socket.timeout:
                return None
        return Datagram(data, src=src, dst=dst)

    #TODO: define a method for retransmission on request-response protocols

    def bind(self, *args):
        """Bind to the addres and port sequence"""
        if self.local.port != 0:
            raise RuntimeError('UDP object already bound to a port')
        addr = Address(*args)
        self.sock.bind(tuple(addr))

    def connect(self, *args):
        """Connect to the address and port sequence"""
        if self.connected:
            raise RuntimeError('UDP object already connected')
        addr = Address(*args)
        self.sock.connect(tuple(addr))
        self.connected = True

    def close(self):
        """Close the low-level socket file descriptor"""
        self.sock.close()

def udp_server(addr, port):
    """Create a new UDP socket bound to address and port"""
    return UDP(bind=(addr, port))

def udp_client(addr, port):
    """Create a new UDP socket connected to address and port"""
    return UDP(connect=(addr, port))
