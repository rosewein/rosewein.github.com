import json
topo=json.load(open('emd_topo.json'))
obj=topo['objects']['seoul_neighborhoods_geo']
GU={"11110":"종로","11140":"중","11170":"용산","11200":"성동","11215":"광진","11230":"동대문","11260":"중랑","11290":"성북","11305":"강북","11320":"도봉","11350":"노원","11380":"은평","11410":"서대문","11440":"마포","11470":"양천","11500":"강서","11530":"구로","11545":"금천","11560":"영등포","11590":"동작","11620":"관악","11650":"서초","11680":"강남","11710":"송파","11740":"강동"}
def S(*a): return set(a)
JN_OUT=S("평창동","구기동","부암동","홍지동","신영동","행촌동","송월동","홍파동","평동","교남동","교북동","무악동","창신동","숭인동")
JN_SDM=S("부암동","홍지동","신영동","행촌동","송월동","홍파동","평동","교남동","교북동","무악동","평창동","구기동")
JG_SDM=S("정동","서소문동","순화동","의주로1가","의주로2가","중림동","만리동1가","만리동2가","충정로1가")
JG_SD=S("신당동","황학동","흥인동","무학동")
SB_DDM_PRE49=lambda n: n in ("성북동","성북동1가","돈암동","종암동") or n.startswith(("동소문동","삼선동","동선동","안암동","보문동"))
MP_YS=S("도화동","마포동","용강동","토정동","대흥동","염리동")
MP_SDM49=S("상암동","중동","성산동","연남동","노고산동")
def assign(p,gu,n):
    g=GU[gu]
    if p<1975:
        if g=="종로": return "서대문" if n in JN_SDM else ("동대문" if n in ("창신동","숭인동") else "종로")
        if g=="중": return "서대문" if n in JG_SDM else ("성동" if n in JG_SD else "중")
        if g=="용산": return "중" if n=="동자동" else "용산"
        if g=="마포":
            if p<1944: return "용산" if n in MP_YS else "서대문"
            return "서대문" if n in MP_SDM49 else "마포"
        if g=="성동":
            if n=="용답동": return "동대문"
            return "성동"
        if g=="동대문":
            if n=="장안동": return "성동"
            return "동대문"
        if g=="성북":
            if p<1949: return "동대문"
            if n.startswith("보문동"): return "동대문"
            if p>=1973 and n=="길음동": return "도봉"
            return "성북"
        if g=="강북": return "도봉" if p>=1973 else "성북"
        if g in ("도봉","노원"): return "도봉" if p>=1973 else "성북"
        if g=="광진": return "성동"
        if g=="중랑": return "성동" if (n=="면목동" and p<1963) else "동대문"
        if g=="송파" and n in ("잠실동","신천동") and p<1963: return "성동"
        if g in ("강남","송파","강동"): return "성동"
        if g=="서초":
            if n in ("내곡동","염곡동","신원동"): return "성동"
            if p>=1973: return "관악" if n=="방배동" else "성동"
            return "영등포"
        if g=="서대문": return "서대문"
        if g=="은평": return "서대문"
        if g=="동작": return "관악" if p>=1973 else "영등포"
        if g=="관악": return "관악" if p>=1973 else "영등포"
        if g in ("영등포","구로","금천","강서","양천"): return "영등포"
    # 1975 이후
    if g=="중랑": return "동대문" if p<1988 else "중랑"
    if g in ("강북",): return "도봉"
    if g=="노원": return "도봉" if p<1988 else "노원"
    if g=="도봉":
        if p>=1988 and p<1989 and n in ("도봉동","창동"): return "노원"
        return "도봉"
    if g=="광진": return "성동" if p<1995 else "광진"
    if g=="서초":
        if p<1980 and n=="방배동": return "관악"
        return "강남" if p<1988 else "서초"
    if g=="강남":
        if 1988<=p<1989 and n=="도곡동": return "서초"
        return "강남"
    if g=="송파": return ("강남" if p<1979 else "강동") if p<1988 else "송파"
    if g=="강동": return "강남" if p<1979 else "강동"
    if g=="은평": return "서대문" if p<1979 else "은평"
    if g=="동작": return "관악" if p<1980 else "동작"
    if g=="구로": return "영등포" if p<1980 else "구로"
    if g=="금천": return ("영등포" if p<1980 else "구로") if p<1995 else "금천"
    if g=="강서": return "영등포" if p<1977 else "강서"
    if g=="양천": return ("영등포" if p<1977 else "강서") if p<1988 else "양천"
    if g=="강북": return "도봉" if p<1995 else "강북"
    return g
# 강북 1995 fix
def assign2(p,gu,n):
    g=GU[gu]
    if p>=1995 and g=="강북": return "강북"
    return assign(p,gu,n)
periods=[(1943,"7구"),(1944,"8구"),(1949,"9구"),(1963,"9구 + 출장소"),(1973,"11구"),(1975,"12구"),(1977,"13구"),(1979,"15구"),(1980,"17구"),(1988,"22구"),(1989,"22구"),(1995,"25구")]
out=[]
for p,label in periods:
    names=[]; idx=[]
    for g in obj['geometries']:
        pr=g['properties']; nm=assign2(p,pr['gu'],pr['nm'])+"구"
        if nm=="중구구": nm="중구"
        if nm not in names: names.append(nm)
        idx.append(names.index(nm))
    out.append({"from":p,"label":label,"names":names,"idx":idx})
    print(p,label,len(names),sorted(names))
json.dump(out,open('gu_periods.json','w'),ensure_ascii=False,separators=(",",":"))
