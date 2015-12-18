# netbuffer.py
# Helper for network data managing


class NetBuffer(bytearray):
    """Parse and forge network data"""

    ##### Static Methods #####
    _encode = lambda s, codec: s.encode() if codec is None else s.encode(codec)
    _decode = lambda d, codec: d.decode() if codec is None else d.decode(codec)

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
    def to_int(data, size=None, signed=None):
        """Convert bytes to integer

        Return the integer value and number of bytes used"""
        size = 1 if size is None else size
        signed = False if signed is None else signed
        value = int.from_bytes(data[:size], 'big', signed=signed)
        return value, size

    @staticmethod
    def from_str(value, size=None, encoding=None):
        """Convert string to bytes

        size = -X --> X bytes used as integer header for size
        size = 0 --> encoded '\x00' added to the end of the bytes after encoding
        size = X --> first X bytes only, filled with 0x00 if needed
        """
        bstr = NetBuffer._encode(value, encoding)
        if size is None:
            return bstr
        length = len(bstr)
        if size < 0:
            size = -size
            bstr = NetBuffer.from_int(length, size) + bstr
        elif size == 0:
            bstr = bstr + NetBuffer._encode('\x00', encoding)
        elif size > 0:
            if size > length:
                bsrt += b'\x00' * (size - length)
            else:
                bstr = bstr[:size]
        return bstr

    @staticmethod
    def to_str(data, size=None, encoding=None):
        if size is None:
            value = NetBuffer._decode(data, encoding)
            size = len(data)
        if size < 0:
            strsize, size = NetBuffer.to_int(data, -size)
            data = data[size:size+strsize]
            value = NetBuffer._decode(data, encoding)
            size += strsize
        elif size == 0:
            NUL = NetBuffer._encode('\x00', encoding)
            head, sep, tail = data.partition(NUL)
            value = NetBuffer._decode(head, encoding)
            size = len(head) + len(sep)
        elif size > 0:
            data = data[:size]
            value = NetBuffer._decode(data, encoding)
        return value, size

    @staticmethod
    def from_bytes_to_bytes(data, size=None):
        if size is None:
            size = len(data)
        return bytes(data[:size]), size
    ##### End of Static Methods #####

    def __init__(self, *args, **kwargs):
        self.int_size = kwargs.pop('int_size', None)
        self.int_signed = kwargs.pop('int_signed', None)
        self.str_size = kwargs.pop('str_size', 0)
        self.str_encoding = kwargs.pop('str_encoding', None)
        self.bytes_size = kwargs.pop('bytes_size', 512)
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
                return self.from_str(*item)

        # bad luck
        raise ValueError('Unexpected object', item)

    def from_bytes(self, item):
        """Return an item and byte size from bytes"""
        if item in [bytes, int, str]:
            item = {'type': item}

        if isinstance(item, dict):
            t = item.pop('type')
            item['data'] = self
            if t is bytes:
                item.setdefault('size', self.bytes_size)
                return self.from_bytes_to_bytes(**item)
            if t is int:
                item.setdefault('size', self.int_size)
                item.setdefault('signed', self.int_signed)
                return self.to_int(**item)
            if t is str:
                item.setdefault('size', self.str_size)
                item.setdefault('encoding', self.str_encoding)
                return self.to_str(**item)
        else:
            item = list(item)
            t = item[0]
            item[0] = self
            if t is bytes:
                if len(item) < 2: item.append(self.bytes_size)
                return self.from_byets_to_bytes(*item)
            if t is int:
                if len(item) < 2: item.append(self.int_size)
                if len(item) < 3: item.append(self.int_signed)
                return self.to_int(*item)
            if t is str:
                if len(item) < 2: item.append(self.str_size)
                if len(item) < 3: item.append(self.str_encoding)
                return self.to_str(*item)
        raise ValueError('Unexpected object', t)


    def append(self, item):
        """Append a single item to the end of the buffer

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

    def pop(self, item):
        """Remove and return an item from the buffer"""
        value, size = self.from_bytes(item)
        del self[:size]
        return value
