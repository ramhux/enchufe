# enchufe.py
# High-level socket API

class Datagram(object):
    """UDP Datagram

    A Datagram has:
    * payload (data)
    * Sourde address:port pair
    * Destination address:port pair
    """

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
