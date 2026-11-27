import re
def norm(nm):
    """나들목 이름 → (바탕 이름, 종류). 종류: JC(분기점) 또는 IC"""
    s=nm.split(";")[0]
    t="JC" if re.search(r"분기점|JCT|JC",s) else "IC"
    s=re.sub(r"\(.*?\)","",s)
    s=re.sub(r"분기점|나들목|하이패스|JCT|JC|IC|TG|요금소|휴게소.*","",s)
    s=s.replace(" ","")
    return s,t
