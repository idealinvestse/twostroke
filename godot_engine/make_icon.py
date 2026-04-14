"""Generate a valid 128x128 PNG icon for Godot project."""
import struct
import zlib

w = h = 128
# Dark blue-grey pixels
rows = b''
for _ in range(h):
    rows += b'\x00' + bytes([100, 100, 110]) * w

def make_chunk(data, chunk_type):
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack('>I', len(data)) + chunk_type + data + struct.pack('>I', crc)

ihdr = make_chunk(struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0), b'IHDR')
idat = make_chunk(zlib.compress(rows), b'IDAT')
iend = make_chunk(b'', b'IEND')

with open('assets/icon.png', 'wb') as f:
    f.write(b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend)

print("Created valid 128x128 icon.png")
