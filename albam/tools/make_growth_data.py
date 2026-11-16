#!/usr/bin/env python3
"""WHO 성장 기준(0~24개월)의 L·M·S 값을 src/growth-data.js 로 만든다.

    python3 tools/make_growth_data.py <pygrowup 의 tables 폴더>

원본: WHO Child Growth Standards(2006)의 월별 표. PyPI 의 pygrowup(UNICEF, BSD) 꾸러미가 JSON 으로 담고 있다:
    pip download pygrowup --no-deps --no-binary :all:   → pygrowup/tables/*.json
한국 2017 소아청소년 성장도표도 만 3세 미만은 이 WHO 기준을 쓴다.
"""
import json
import sys
from pathlib import Path

MEASURES = {'weight': 'wfa', 'height': 'lhfa', 'head': 'hcfa'}   # 체중(kg) · 누운 키(cm) · 머리둘레(cm)
SEXES = {'boy': 'boys', 'girl': 'girls'}
MONTHS = 24


def table(folder, code, sex):
    name = f'{code}_{sex}_0_2_zscores.json' if code == 'lhfa' else f'{code}_{sex}_0_5_zscores.json'
    rows = {int(r['Month']): r for r in json.loads((folder / name).read_text())}
    return [[float(rows[m][k]) for k in ('L', 'M', 'S')] for m in range(MONTHS + 1)]


def main():
    folder = Path(sys.argv[1])
    out = ['// WHO 성장 기준(Child Growth Standards, 2006) 0~24개월의 월별 L·M·S.',
           '// tools/make_growth_data.py 가 만든 파일이다. 손으로 고치지 않는다.',
           '// 칸 번호 = 개월(0~24), 값 = [L, M, S]. 체중 kg, 키(누운 키)·머리둘레 cm.',
           'export const WHO_LMS = {']
    for measure, code in MEASURES.items():
        out.append(f'  {measure}: {{')
        for sex, word in SEXES.items():
            rows = ', '.join(json.dumps(r) for r in table(folder, code, word))
            out.append(f'    {sex}: [{rows}],')
        out.append('  },')
    out.append('};')
    Path(__file__).resolve().parent.parent.joinpath('src', 'growth-data.js').write_text('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
