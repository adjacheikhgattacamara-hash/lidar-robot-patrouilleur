"""Pilote minimal LiDAR LDROBOT LD14P (série 230400 bauds, trames de 47 octets)."""
import struct
import serial  # pip install pyserial

PORT_DEFAUT = "/dev/ttyUSB0"
BAUDS = 230400
TAILLE = 47


def _crc_table():
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = ((c << 1) ^ 0x4D) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        t.append(c)
    return t


_CRC = _crc_table()


def crc8(data):
    c = 0
    for b in data:
        c = _CRC[(c ^ b) & 0xFF]
    return c


def decoder_trame(trame):
    """12 tuples (angle_deg, distance_mm, intensite) ou None si invalide."""
    if len(trame) != TAILLE or crc8(trame[:46]) != trame[46]:
        return None
    debut = struct.unpack_from("<H", trame, 4)[0] / 100.0
    fin = struct.unpack_from("<H", trame, 42)[0] / 100.0
    if fin < debut:
        fin += 360.0
    pas = (fin - debut) / 11
    pts = []
    for i in range(12):
        d, inten = struct.unpack_from("<HB", trame, 6 + 3 * i)
        pts.append(((debut + pas * i) % 360.0, d, inten))
    return pts


class LD14P:
    def __init__(self, port=PORT_DEFAUT):
        self.port = port
        self._ser = None

    def __enter__(self):
        self._ser = serial.Serial(self.port, BAUDS, timeout=1)
        return self

    def __exit__(self, *exc):
        if self._ser:
            self._ser.close()
            self._ser = None

    def trames(self):
        buf = bytearray()
        while True:
            buf += self._ser.read(self._ser.in_waiting or 1)
            while len(buf) >= TAILLE:
                if buf[0] != 0x54 or buf[1] != 0x2C:
                    del buf[0]
                    continue
                pts = decoder_trame(bytes(buf[:TAILLE]))
                if pts is None:
                    del buf[0]
                    continue
                del buf[:TAILLE]
                yield pts

    def scans(self):
        """Un scan = un tour complet de 360 degres."""
        scan, dernier = [], None
        for pts in self.trames():
            a0 = pts[0][0]
            if dernier is not None and a0 < dernier and scan:
                yield scan
                scan = []
            scan.extend(pts)
            dernier = a0
