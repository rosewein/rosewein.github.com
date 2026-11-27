# Minimal EGG (ESTsoft) extractor: handles store(0) / deflate(1) / bzip2(2) / lzma(4), unencrypted, non-solid
import sys, struct, zlib, bz2, lzma, os
src, out = sys.argv[1], sys.argv[2]
d = open(src,'rb').read()
os.makedirs(out, exist_ok=True)
FILE=0x0A8590E3; NAME=0x0A8591AC; BLOCK=0x02B50C13; END=0x08E28222
i = 0
name = None
while i < len(d):
    sig = struct.unpack_from('<I', d, i)[0]
    if sig == NAME:
        bitflag = d[i+4]; size = struct.unpack_from('<H', d, i+5)[0]
        p = i+7
        if bitflag & 0x08: p += 4  # locale
        if bitflag & 0x10: p += 4  # parent path id
        raw = d[p:i+7+size]
        name = raw.decode('utf-8', 'replace') if not (bitflag & 0x08) else raw.decode('cp949','replace')
        i = i+7+size; continue
    if sig == BLOCK:
        meth, hint, usize, csize, crc = struct.unpack_from('<BBIII', d, i+4)
        p = i+4+14
        assert struct.unpack_from('<I', d, p)[0] == END, 'no end after block header'
        p += 4
        data = d[p:p+csize]
        if meth == 0: u = data
        elif meth == 1: u = zlib.decompress(data, -15)
        elif meth == 2: u = bz2.decompress(data)
        elif meth == 4:
            # EGG LZMA: 4-byte prefix (version) + 5-byte props, raw lzma1
            props = data[4:9]
            filt = [{'id': lzma.FILTER_LZMA1, 'dict_size': struct.unpack('<I', props[1:5])[0],
                     'lc': props[0] % 9, 'lp': (props[0]//9) % 5, 'pb': props[0]//45}]
            u = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=filt).decompress(data[9:], usize)
        else:
            raise SystemExit(f'unsupported method {meth} for {name}')
        ok = (zlib.crc32(u) & 0xffffffff) == crc
        safe = os.path.basename(name.replace('\\','/')) if name else f'file{i}'
        open(os.path.join(out, safe), 'wb').write(u)
        print(f'{safe}\tmethod={meth}\tusize={usize}\tgot={len(u)}\tcrc_ok={ok}')
        i = p + csize; name = None; continue
    i += 1
