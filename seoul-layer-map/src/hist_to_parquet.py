"""토지이동이력정보(V-World dsId=13, AL_D157_11_YYYYMMDD.zip 안의 CSV) → parquet(parcel_lineage.py 입력).
    python3 -I hist_to_parquet.py <AL_D157 CSV 또는 zip> <출력 hist.parquet>
CSV는 CP949, 모든 칸을 글자로 읽는다(고유번호 앞자리 0 보존)."""
import sys, zipfile, io, pandas as pd
src, out = sys.argv[1], sys.argv[2]
if src.lower().endswith(".zip"):
    z = zipfile.ZipFile(src); name = max((i for i in z.infolist() if i.filename.lower().endswith(".csv")), key=lambda i: i.file_size)
    f = io.BytesIO(z.read(name))
else:
    f = src
pd.read_csv(f, encoding="cp949", dtype=str).to_parquet(out)
print("저장", out)
