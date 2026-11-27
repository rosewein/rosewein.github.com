"""station_rings.py 결과(json)를 역 중앙값으로 묶는 함수와 요약 출력."""
import json, sys, numpy as np
R = json.load(open(sys.argv[1])); S = R['stations']; sm = R['seoul_med']; ssp = R['seoul_sp']
RINGS = ['0-250', '250-500', '500-1000']
def series(s, var, loc, ring):
    T = s['T']; out = []
    for t in range(T - 5, T + 6):
        yr = s['years'][str(t)][loc]
        if var in ('A_seoul', 'A_ctrl'):
            v, n = yr['cs'][ring]; b, _ = s['years'][str(T-5)][loc]['cs'][ring]
            if var == 'A_seoul': ref, ref0 = sm[str(t)], sm[str(T-5)]
            else:
                ref = yr['cs']['ctrl'][0]; ref0 = s['years'][str(T-5)][loc]['cs']['ctrl'][0]
            out.append(None if None in (v, b, ref, ref0) else np.log2(v / ref) - np.log2(b / ref0))
        else:
            v, n = yr['sp'][ring]
            ref = ssp[f'{T-5}-{t}'] if var == 'B_seoul' else yr['sp']['ctrl'][0]
            out.append(None if v is None or ref is None else v - ref)
    return out
def agg(var, loc, ring):
    arr = np.array([[np.nan if v is None else v for v in series(s, var, loc, ring)] for s in S], float)
    return np.nanmedian(arr, axis=0), np.sum(~np.isnan(arr), axis=0)
if __name__ == '__main__':
    for loc in ('exact', 'all'):
        for var in ('A_seoul', 'A_ctrl', 'B_seoul', 'B_ctrl'):
            row = []
            for ring in RINGS:
                med, n = agg(var, loc, ring)
                row.append(f'{ring}: T+5 {100*(2**med[10]-1):+5.1f}% (T0 {100*(2**med[5]-1):+5.1f}%, n={n[10]})')
            print(loc, var, ' | '.join(row))
