"""지도 글꼴을 저장소에 직접 담는다(v1.4.4부터). build.py가 부른다.

구글 폰트는 한글을 수십 개 조각(unicode-range)으로 나눠 보내서, 조각 하나가 늦거나 빠지면
한 낱말 안에서도 몇 글자만 다른 글꼴로 찍힌다(예: 「서울 시내버스 규모」의 '시'·'스'만 [119] 조각).
그래서 페이지에 실제로 쓰이는 글자만 담은 woff2를 굵기마다 하나씩 만들어 fonts/에 둔다.

- 원본: google/fonts 저장소의 TTF(커밋을 고정, sha256으로 확인). 받은 원본은 RAW/fonts에 둔다.
- Hahmlet(제목 글꼴, OFL 1.1, 이름 예약 없음): h1·h2·연표 시기 제목·연도 숫자에 쓰는 글자만. 가변 글꼴에서 500·700 굵기를 떼어 냄
  (가변 그대로 두면 글자가 적어도 61KB라, 굵기별 고정 글꼴 두 개가 더 작다).
- IBM Plex Sans KR·Mono(OFL 1.1, 'Plex'가 예약된 이름): 글자를 덜어 낸 것은 수정본이라 예약된 이름을 쓸 수 없다.
  그래서 글꼴 안의 이름을 'SLM Sans KR'·'SLM Mono'로 바꾸고, CSS에서도 그 이름으로 부른다.
- 글자 모음이 그대로면(fonts/manifest.json) 다시 만들지 않는다. fontTools가 없거나 원본을 못 받으면,
  있는 파일로 두고 빠지는 글자 수를 알린다.
"""
import hashlib, json, os, sys, urllib.request

COMMIT = "6ebe737e44fd64ee736bbc6feed6136a6dbfd222"   # google/fonts, 2026-11-26에 받은 main
BASE = f"https://raw.githubusercontent.com/google/fonts/{COMMIT}/"
SRC = {   # 원본 파일: (저장소 안 경로, sha256)
    "hahmlet": ("ofl/hahmlet/Hahmlet%5Bwght%5D.ttf", "892bffe530255770a7435226154a02f519055ff6bedf64254f37f21d15a59279"),
    "sans400": ("ofl/ibmplexsanskr/IBMPlexSansKR-Regular.ttf", "53750379270312368cf7641901f43a98dd892e3d9d5798cf25cdc245c85c71c0"),
    "sans500": ("ofl/ibmplexsanskr/IBMPlexSansKR-Medium.ttf", "4a7130f56ce50bf10f9d383f624e50bad2c80bebc63e51f4269ece2c7d919166"),
    "sans600": ("ofl/ibmplexsanskr/IBMPlexSansKR-SemiBold.ttf", "823c1956adf56c27c06b062725dfce23f266e4fd1366290f2957c8407482a817"),
    "mono400": ("ofl/ibmplexmono/IBMPlexMono-Regular.ttf", "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46"),
    "mono500": ("ofl/ibmplexmono/IBMPlexMono-Medium.ttf", "a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755"),
    "ofl_hahmlet": ("ofl/hahmlet/OFL.txt", "ddadb10d28a303e3ef3b1f7ec55d3027903b9ec566d2f87d3ee03f3c87c91711"),
    "ofl_plex": ("ofl/ibmplexsanskr/OFL.txt", "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da"),
}
# 만들 파일: 이름 → (원본, 글자 모음, 이름 바꾸기[, 가변 글꼴에서 뗄 굵기])
OUTS = {
    "hahmlet-500.woff2": ("hahmlet", "display", None, 500),
    "hahmlet-700.woff2": ("hahmlet", "display", None, 700),
    "slm-sans-kr-400.woff2": ("sans400", "page", ("IBM Plex Sans KR", "SLM Sans KR")),
    "slm-sans-kr-500.woff2": ("sans500", "page", ("IBM Plex Sans KR", "SLM Sans KR")),
    "slm-sans-kr-600.woff2": ("sans600", "page", ("IBM Plex Sans KR", "SLM Sans KR")),
    "slm-mono-400.woff2": ("mono400", "page", ("IBM Plex Mono", "SLM Mono")),
    "slm-mono-500.woff2": ("mono500", "page", ("IBM Plex Mono", "SLM Mono")),
}
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))


def _src(key, cache):
    path, sha = SRC[key]
    os.makedirs(cache, exist_ok=True)
    fn = os.path.join(cache, path.split("/")[1] + "__" + path.rsplit("/", 1)[1].replace("%5B", "[").replace("%5D", "]"))
    if not os.path.exists(fn):
        print("fonts: 원본 받는 중", path, file=sys.stderr)
        with urllib.request.urlopen(BASE + path, timeout=60) as r:
            open(fn, "wb").write(r.read())
    got = hashlib.sha256(open(fn, "rb").read()).hexdigest()
    if got != sha:
        raise RuntimeError(f"fonts: {fn}의 sha256이 다름({got[:12]}…)")
    return fn


def _rename(font, old, new):
    o2, n2 = old.replace(" ", ""), new.replace(" ", "")
    for r in font["name"].names:
        if r.nameID in (1, 3, 4, 6, 16, 17, 18, 21, 22):
            s = r.toUnicode()
            s2 = s.replace(old, new).replace(o2, n2)
            if s2 != s: r.string = s2
    for r in font["name"].names:
        if r.nameID in (1, 3, 4, 6, 16, 21) and "Plex" in r.toUnicode():
            raise RuntimeError("fonts: 예약된 이름이 남음: " + r.toUnicode())
    if "CFF " in font:   # CFF 글꼴이면 그 안의 이름도
        cff = font["CFF "].cff
        cff.fontNames = [n.replace(o2, n2) for n in cff.fontNames]


def _make(src, text, out, rename, wght=None):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    opt = subset.Options()
    opt.flavor = "woff2"; opt.layout_features = ["*"]; opt.name_IDs = ["*"]; opt.name_languages = ["*"]
    opt.notdef_outline = True; opt.drop_tables += ["DSIG"]
    f = TTFont(src, recalcTimestamp=False)
    if wght:
        from fontTools.varLib import instancer
        f = instancer.instantiateVariableFont(f, {"wght": wght})
        f["OS/2"].usWeightClass = wght
    s = subset.Subsetter(opt); s.populate(text=text); s.subset(f)
    if rename: _rename(f, *rename)
    f.flavor = "woff2"
    f.save(out)


def _covered(fn):
    from fontTools.ttLib import TTFont
    return set(TTFont(fn).getBestCmap())


def build(page_text, display_text, outdir, cache):
    """page_text·display_text에 든 글자로 글꼴 조각을 만들고, 주소 뒤에 붙일 짧은 판 번호를 돌려준다."""
    sets = {"page": "".join(sorted(set(page_text) | set(ASCII))),
            "display": "".join(sorted(set(display_text) | set(ASCII)))}
    key = hashlib.sha1(json.dumps([COMMIT, sets, sorted(OUTS.items())], ensure_ascii=False).encode()).hexdigest()[:10]
    man_fn = os.path.join(outdir, "manifest.json")
    man = json.load(open(man_fn)) if os.path.exists(man_fn) else {}
    have = all(os.path.exists(os.path.join(outdir, n)) for n in OUTS)
    if man.get("key") == key and have:
        print("fonts: 글자 모음이 그대로라 다시 만들지 않음", key, file=sys.stderr)
        return key
    try:
        os.makedirs(outdir, exist_ok=True)
        for name, (src, which, rename, *w) in OUTS.items():
            _make(_src(src, cache), sets[which], os.path.join(outdir, name), rename, *w)
        open(os.path.join(outdir, "OFL-Hahmlet.txt"), "wb").write(open(_src("ofl_hahmlet", cache), "rb").read())
        open(os.path.join(outdir, "OFL-IBM-Plex.txt"), "wb").write(open(_src("ofl_plex", cache), "rb").read())
    except Exception as e:   # fontTools가 없거나 원본을 못 받으면 있는 파일로 두고 빠지는 글자를 알린다
        print("fonts: 새로 만들지 못함 —", repr(e)[:200], file=sys.stderr)
        try:
            for name, (src, which, *_) in OUTS.items():
                fn = os.path.join(outdir, name)
                if not os.path.exists(fn): print("fonts: 파일 없음", name, file=sys.stderr); continue
                miss = [c for c in sets[which] if ord(c) not in _covered(fn) and ord(c) in _covered_src_guess(src)]
                if miss: print(f"fonts: {name}에 없는 글자 {len(miss)}개:", "".join(miss[:40]), file=sys.stderr)
        except Exception:
            pass
        return man.get("key", "0")
    sizes = {n: os.path.getsize(os.path.join(outdir, n)) for n in OUTS}
    json.dump({"key": key, "source": f"google/fonts@{COMMIT}", "chars": {k: len(v) for k, v in sets.items()}, "bytes": sizes},
              open(man_fn, "w"), ensure_ascii=False, indent=1)
    print("fonts: 새로 만듦", key, {n: f"{b // 1024}KB" for n, b in sizes.items()}, file=sys.stderr)
    return key


def _covered_src_guess(src):
    # 원본이 없을 때는 원본이 그 글자를 가졌는지 알 수 없으므로, 한글·영문·문장부호는 가졌다고 본다
    return set(range(0x20, 0x7F)) | set(range(0xAC00, 0xD7A4)) | set(range(0x2000, 0x2070)) if src.startswith("sans") else set(range(0x20, 0x7F))
