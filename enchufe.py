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


class NetBuffer(bytearray):
    """Parse and forge network data"""

    ##### Static Methods #####
    @staticmethod
    def from_int(value, size=None, signed=None):
        """Convert integer to bytes

        size = 0 or None --> size is calculated automatically
        size = X --> X bytes size"""
        size = 0 if size is None else size
        signed = value < 0 if signed is None else signed
        if size < 0:
            raise ValueError('Invalid size', size)
        if size == 0:
            size = value.bit_length()
            size += 1 if signed else 0
            size = ((size - 1) // 8) + 1
        return value.to_bytes(size, 'big', signed=signed)

    @staticmethod
    def from_str(value, size=None, encoding=None):
        """Convert string to bytes

        size = -X --> X bytes used as integer header for size
        size = 0 --> 0x00 added to the end of the bytes
        size = X --> first X bytes only, filled with 0x00 if needed
        """
        bstr = value.encode() if encoding is None else value.encode(encoding)
        if size is None:
            return bstr
        length = len(bstr)
        if size < 0:
            size = -size
            bstr = NetData.integer(length, size) + bstr
        elif size == 0:
            bstr = bstr + b'\x00'
        elif size > 0:
            bstr = bstr + (size - length) * b'\x00' if size > length else bstr[:size]
        return bstr
    ##### End of Static Methods #####

    def __init__(self, *args, **kwargs):
        self.int_size = kwargs.pop('int_size', None)
        self.int_signed = kwargs.pop('int_signed', None)
        self.str_size = kwargs.pop('str_size', None)
        self.str_encoding = kwargs.pop('str_encoding', None)
        if len(kwargs) > 0:
            msg = "'{}' is an invalid keyword argument"
            raise TypeError(msg.format(kwargs.popitem()[0]))
        super().__init__(*args)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, bytes(self))

    __str__ = __repr__

    def to_bytes(self, item):
        """Return bytes form item

        if item is bytes, bytearray or memoryview, return bytes(x)
        if item is int or str, convert to bytes using defaults
        if item is dict, use item values as keyword arguments
        if item is a sequence, use item values as positional arguments
        """
        # x is binary data
        if isinstance(item, (bytes, bytearray, memoryview)):
            return bytes(item)

        # Just a value, use defaults
        if isinstance(item, (int, str)):
            item = {'value': item}

        # x is a dict as {'value': x, 'xxx_size': y, ...}
        if isinstance(item, dict):
            if isinstance(item['value'], int):
                item.setdefault('size', self.int_size)
                item.setdefault('signed', self.int_signed)
                return self.from_int(**item)
            if isinstance(item['value'], str):
                item.setdefault('size', self.str_size)
                item.setdefault('encoding', self.str_encoding)
                return self.from_str(**item)

        else: # a sequence (positional arguments)
            item = list(item)
            if isinstance(item[0], int):
                if len(item) < 2: item.append(self.int_size)
                if len(item) < 3: item.append(self.int_signed)
                return self.from_int(*item)
            if isinstance(item[0], str):
                if len(item) < 2: item.append(self.str_size)
                if len(item) < 3: item.append(self.str_encoding)
                return self.str(*item)

        # bad luck
        raise ValueError('Unexpected object', x)

    def append(self, item):
        """Append a single item (int or str) to the end

        The item is used as the argument of to_bytes()"""
        super().extend(self.to_bytes(item))

    def extend(self, item_list):
        """Append all the elements from a sequence to the end

        Every item is used as the argument of to_bytes()"""
        for item in item_list:
            self.append(item)

    def insert(self, index, item):
        """Insert a single item as bytes before the given index"""
        item = self.to_bytes(item)
        for index, value in enumerate(item, index):
            super().insert(index, value)

    def pop(self, index=0):
        """Remove and return an item from the buffer


        """
        pass #TODO


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
