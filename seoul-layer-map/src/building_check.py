"""새 건물 자료 대조: 대장으로 쌓은 해마다의 연면적 합계를 서울시 「건축물 연면적 통계」와 견준다.

    python3 src/building_check.py <표제부·폐쇄말소대장 CSV 폴더> <연면적 통계 CSV>

- 대장 쪽: 그 해까지 사용승인된 지금 대장 건물 + 그 해까지 사용승인되고 그 해 뒤에 말소(말소·일부말소)된 건물.
  사용승인일이 빈 줄은 뺀다. 한 동 연면적이 100만㎡를 넘는 줄은 building.py와 같이 1/1000로 고친다.
- 통계 쪽: 서울 열린데이터광장 「서울시 건축물 연면적 통계」(DT201004K030006)를 통계표 「다운로드」에서 CSV로 받은 것.
  '서울시 / 소계' 줄의 '건축물총면적' 칸을 쓴다.
- 결과는 화면에 표로 찍기만 한다(지도에는 쓰지 않음). 2026-11-26 결과는 HANDOFF.md 「건물 레이어」에 있다.
"""
import csv, io, os, sys
from collections import Counter

AREA_MAX = 1_000_000


def rows(path):
    raw = open(path, "rb").read(300000)
    enc = min(("cp949", "utf-8-sig", "utf-8"), key=lambda e: raw.decode(e, errors="replace").count("�"))
    with open(path, encoding=enc, errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def year(s):
    s = (s or "").strip()
    return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() and 1800 <= int(s[:4]) <= 2100 else None


def area(s):
    try:
        v = float(s or 0)
    except ValueError:
        return 0.0
    return v / 1000 if v > AREA_MAX else v


def main(src, stats):
    cur, gone = Counter(), Counter()
    for f in sorted(os.listdir(src)):
        if not f.endswith(".csv") or "표제부" not in f or "총괄" in f:
            continue
        is_gone = "폐쇄" in f or "말소" in f
        for r in rows(os.path.join(src, f)):
            y = year(r.get("사용승인일자"))
            if y is None:
                continue
            if is_gone:
                if r.get("폐쇄말소구분코드명") not in ("말소", "일부말소"):
                    continue
                gone[(y, year(r.get("폐쇄말소일자")))] += area(r.get("연면적"))
            else:
                cur[y] += area(r.get("연면적"))
    t = list(csv.reader(io.StringIO(open(stats, "rb").read().decode("utf-8-sig"))))
    seoul = next(r for r in t if r[0].strip('"') == "서울시" and r[1] == "소계")
    off = {int(y): float(v) for y, it, v in zip(t[0][2:], t[1][2:], seoul[2:]) if it.startswith("건축물총면적") and v not in ("", "-")}
    print("해\t통계(백만㎡)\t대장(백만㎡)\t대장/통계")
    for T in sorted(off):
        rec = sum(v for y, v in cur.items() if y <= T) + sum(v for (y, c), v in gone.items() if y <= T and c is not None and c > T)
        print(f"{T}\t{off[T] / 1e6:.1f}\t{rec / 1e6:.1f}\t{rec / off[T] * 100:.1f}%")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
