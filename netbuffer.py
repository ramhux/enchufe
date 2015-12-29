# netbuffer.py
# Helper for network data managing

import copy
import collections
import inspect
import types

_encode = lambda s, codec: s.encode() if codec is None else s.encode(codec)
_decode = lambda d, codec: d.decode() if codec is None else d.decode(codec)

def _block(data, size=512):
    if size is None:
        size = len(data)
    return bytes(data[:size]), size

def _signature(func):
    args = inspect.signature(func)
    args = collections.OrderedDict(args.parameters.items())
    for key in args:
        args[key] = args[key].default
    return args

def objectmethod(obj, name, func):
    def omdecorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    method = types.MethodType(omdecorator(func), obj)
    object.__setattr__(obj, name, method)

def defaultsdecorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def _dict_default(obj, type_, argname):
    if type(type_) is str:
        for key in obj._defaults:
            if key.__name__ == type_:
                type_ = key
                break
    if type_ not in obj._defaults:
        raise TypeError("Invalid type: '{}'".format(type_))
    args = obj._defaults[type_]
    if argname not in args or argname in ['to', 'from']:
        raise ValueError("Invaild argname: '{}'".format(argname))
    return args

def _get_default(obj, type_, argname):
    args = _dict_default(obj, type_, argname)
    return args[argname]

def _set_default(obj, type_, argname, value):
    args = _dict_default(obj, type_, argname)
    args[argname] = value

class NetBuffer(bytearray):
    """Parse and forge network data"""
    _defaults = { bytes: {'to': _block, 'size': 512} }

    ##### Class Methods #####
    get_default = classmethod(_get_default)
    set_default = classmethod(_set_default)

    @classmethod
    def register_class(cls, type_, func_from, func_to):
        if type(type_) is not type:
            raise TypeError("Unexpected type object: '{}'".format(type_))
        if type_ in cls._defaults:
            raise ValueError("'{}' already registered".format(type_.__name__))
        empty = inspect.Signature.empty
        args_from = _signature(func_from)
        args_to = _signature(func_to)
        try:
            name, default = args_from.popitem(last=False)
            assert name == 'value' and default is empty
            assert 'to' not in args_from and 'from' not in args_from
            assert empty not in args_from.values()
        except AssertionError:
            raise TypeError("Invalid func_from signature")
        try:
            name, default = args_to.popitem(last=False)
            assert name == 'data' and default is empty
            assert 'to' not in args_to and 'from' not in args_to
            assert empty not in args_to.values()
        except AssertionError:
            raise TypeError("Invalid func_to signature")
        common_args = set(args_from) & set(args_to)
        try:
            for argname in common_args:
                assert args_to[argname] == args_from[argname]
        except AssertionError:
            raise TypeError("Common arguments must have common defaults")
        defaults = {'to': func_to, 'from': func_from}
        defaults.update(args_from)
        defaults.update(args_to)
        cls._defaults[type_] = defaults

    @classmethod
    def drop_class(cls, type_):
        if type_ in cls._defaults:
            del cls._defaults[type_]
        else:
            raise TypeError("'{}' not registered")
    ##### End of Class Methods #####

    def __init__(self, data=b'', **kwargs):
        if isinstance(data, str):
            data = bytes.fromhex(data)
        super().__init__(data)

        object.__setattr__(self, '_defaults', copy.deepcopy(self._defaults))

        objectmethod(self, 'get_default', _get_default)
        objectmethod(self, 'set_default', _set_default)

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

    def __getattr__(self, name):
        typename, sep, argname = name.partition('_')
        try:
            r = self.get_default(typename, argname)
            return r
        except (TypeError, ValueError):
            pass
        raise AttributeError("Invalid attribute name: '{}'".format(name))

    def __setattr__(self, name, value):
        typename, sep, argname = name.partition('_')
        try:
            self.set_default(typename, argname)
            return
        except (TypeError, ValueError):
            pass
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

##### NetBuffer int converter #####
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

NetBuffer.register_class(int, from_int, to_int)
##### End of NetBuffer int converter #####

##### NetBuffer str converter #####
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

NetBuffer.register_class(str, from_str, to_str)
##### End of NetBuffer str converter #####

##### NetBuffer bool converter #####
def from_bool(value, size=1):
    value = int(value)
    return value.to_bytes(size, 'big')

def to_bool(data, size=1):
    value = int.from_bytes(data[:size], 'big')
    return bool(value), size

NetBuffer.register_class(bool, from_bool, to_bool)
##### End of NetBuffer bool converter #####
