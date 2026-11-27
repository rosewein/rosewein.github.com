# usage: extract.py ZIP OUTDIR  -> MOCT_LINK*.{shp,shx,dbf,prj,cpg} 를 OUTDIR/MOCT_LINK.<ext> 로 풀기
import zipfile, sys, os, shutil
z = zipfile.ZipFile(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
got = []
for i in z.infolist():
    n = i.filename.split('/')[-1]
    base, _, ext = n.rpartition('.')
    if base.upper().startswith('MOCT_LINK') and ext.lower() in ('shp', 'shx', 'dbf', 'prj', 'cpg'):
        with z.open(i) as src, open(os.path.join(out, 'MOCT_LINK.' + ext.lower()), 'wb') as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        got.append(n)
print(got)
