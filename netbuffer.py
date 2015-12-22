# netbuffer.py
# Helper for network data managing

import copy

_encode = lambda s, codec: s.encode() if codec is None else s.encode(codec)
_decode = lambda d, codec: d.decode() if codec is None else d.decode(codec)


def block(data, size=512):
    if size is None:
        size = len(data)
    return bytes(data[:size]), size

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

def to_int(data, size=None, signed=None):
    """Convert bytes to integer

    Return the integer value and number of bytes used"""
    size = 1 if size is None else size
    signed = False if signed is None else signed
    #FIXME b'' returns 0
    value = int.from_bytes(data[:size], 'big', signed=signed)
    return value, size

def from_str(value, size=0, encoding=None):
    """Convert string to bytes

    size = -X --> X bytes used as integer header for size
    size = 0 --> encoded '\x00' added to the end of the bytes after encoding
    size = X --> first X bytes only, filled with 0x00 if needed
    """
    bstr = _encode(value, encoding)
    if size is None:
        return bstr
    length = len(bstr)
    if size < 0:
        size = -size
        bstr = from_int(length, size) + bstr
    elif size == 0:
        bstr = bstr + _encode('\x00', encoding)
    elif size > 0:
        if size > length:
            bsrt += b'\x00' * (size - length)
        else:
            bstr = bstr[:size]
    return bstr

def to_str(data, size=0, encoding=None):
    if size is None:
        value = _decode(data, encoding)
        size = len(data)
    if size < 0:
        strsize, size = to_int(data, -size)
        data = data[size:size+strsize]
        value = _decode(data, encoding)
        size += strsize
    elif size == 0:
        NUL = _encode('\x00', encoding)
        head, sep, tail = data.partition(NUL)
        value = _decode(head, encoding)
        size = len(head) + len(sep)
    elif size > 0:
        data = data[:size]
        value = _decode(data, encoding)
    return value, size

class NetBuffer(bytearray):
    """Parse and forge network data"""
    _defaults = { bytes: {'to': block, 'size': 512} }
    _defaults[int] = {'to': to_int, 'from': from_int, 'size': None, 'signed': None}
    _defaults[str] = {'to': to_str, 'from': from_str, 'size': 0, 'encoding': None}

    def __init__(self, data=b'', **kwargs):
        if isinstance(data, str):
            data = bytes.fromhex(data)
        super().__init__(data)

        self._defaults = copy.deepcopy(self._defaults)

        for key in kwargs:
            try:
                setattr(self, key, kwargs[key])
            except AttributeError:
                msg = "'{}' is an invalid keyword argument"
                raise TypeError(msg.format(key))

    def __repr__(self):
        s = repr(self.hex()) if len(self) > 0 else ''
        return '{}({})'.format(self.__class__.__name__, s)

    __str__ = __repr__

    def _defaults_dict(self, typename):
        for key in self._defaults:
            if typename == key.__name__:
                return self._defaults[key]

    def __getattr__(self, name):
        typename, sep, argname = name.partition('_')
        if sep == '_' and argname not in ['to', 'from']:
            args = self._defaults_dict(typename)
            if argname in args:
                return args[argname]
        raise AttributeError("Invalid attribute name: '{}'".format(name))

    def __setattr__(self, name, value):
        typename, sep, argname = name.partition('_')
        if sep == '_' and argname not in ['to', 'from']:
            args = self._defaults_dict(typename)
            if args is not None and argname in args:
                args[argname] = value
                return
        if hasattr(self, name):
            object.__setattr__(self, name, value)
            return
        raise AttributeError("Invalid attribute name: '{}'".format(name))

    def _to_bytes(self, item):
        """Return bytes form item

        if item is bytes, bytearray or memoryview, return bytes(x)
        if item is int or str, convert to bytes using defaults
        if item is dict, use item values as keyword arguments
        if item is a sequence, use item values as positional arguments
        """
        # item is binary data
        if isinstance(item, (bytes, bytearray, memoryview)):
            return bytes(item)

        if type(item) in self._defaults:
            d = self._defaults[type(item)]
            func = d['from']
            return func(item)

        # bad luck
        raise TypeError('Unexpected object', item)

    def _from_bytes(self, item):
        """Return an item and byte size from bytes"""
        if item in self._defaults:
            item = {'type': item}

        ismapping = False
        try:
            _type = item['type']
            ismapping = True
        except TypeError:
            _type = item[0]

        if _type not in self._defaults:
            raise TypeError('Unexpected Object', item)

        if ismapping: # item is a dict-like object
            mapping = dict(item)
            del mapping['type']
            mapping['data'] = bytes(self)
            func = self._defaults[_type]['to']
            return func(**mapping)

        else: # item is a sequence
            seq = list(item)
            seq[0] = bytes(self)
            func = self._defaults[_type]['to']
            return func(*seq)

    def append(self, item):
        """Append a single item to the end of the buffer

        The item is used as the argument of to_bytes()"""
        super().extend(self._to_bytes(item))

    def extend(self, item_list):
        """Append all the elements from a sequence to the end

        Every item is used as the argument of to_bytes()"""
        for item in item_list:
            self.append(item)

    def insert(self, index, item):
        """Insert a single item as bytes before the given index"""
        item = self._to_bytes(item)
        for index, value in enumerate(item, index):
            super().insert(index, value)

    def pop(self, item):
        """Remove and return an item from the buffer"""
        value, size = self._from_bytes(item)
        del self[:size]
        return value
