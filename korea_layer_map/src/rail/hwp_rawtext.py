# Raw HWP5 text extractor: reads BodyText/Section* records, prints PARA_TEXT (tag 67); marks table cell boundaries (LIST_HEADER tag 72)
import sys, zlib, struct, olefile
ole = olefile.OleFileIO(sys.argv[1])
hdr = ole.openstream('FileHeader').read()
compressed = bool(struct.unpack_from('<I', hdr, 36)[0] & 1)
secs = sorted([e for e in ole.listdir() if e[0]=='BodyText'], key=lambda e: int(e[1][7:]))
for s in secs:
    data = ole.openstream(s).read()
    if compressed: data = zlib.decompress(data, -15)
    i = 0
    while i + 4 <= len(data):
        h = struct.unpack_from('<I', data, i)[0]; i += 4
        tag = h & 0x3ff; lvl = (h >> 10) & 0x3ff; size = h >> 20
        if size == 0xfff: size = struct.unpack_from('<I', data, i)[0]; i += 4
        body = data[i:i+size]; i += size
        if tag == 72: print('<CELL>', end='')   # LIST_HEADER (cell start)
        elif tag == 77: print('\n<TABLE>')      # TABLE
        elif tag == 67:
            out=[]; j=0
            while j+2 <= len(body):
                c = struct.unpack_from('<H', body, j)[0]
                if c < 32:
                    if c in (0,10,13): j += 2
                    else: j += 16
                    if c in (10,13): out.append(' ')
                    continue
                out.append(chr(c)); j += 2
            print(''.join(out).strip(), end=' ')
        elif tag == 66: print()  # PARA_HEADER -> newline
