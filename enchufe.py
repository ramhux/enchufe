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
