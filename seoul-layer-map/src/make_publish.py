"""아티팩트용 조각(<title>부터 본문 끝까지)을 공개용 완전한 문서(index.html)로 감싼다.
build.py가 wrap()을 불러 쓴다. 따로 쓸 때: python3 src/make_publish.py <조각.html> <index.html 경로>"""
import re, sys

DESC = "1899년 경인선과 전차부터 지하철·철도·버스, 1990년 이후 땅값(공시지가)까지, 서울의 교통망과 시역·행정구역, 땅값이 바뀌어 온 과정을 연도별 레이어로 겹쳐 보는 지도"


def wrap(html):
    html = html.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
    m = re.match(r'\s*<title>(.*?)</title>\n', html)
    title = m.group(1); body = html[m.end():]
    k = body.index('<style>'); pre, rest = body[:k], body[k:]
    e = rest.index('</style>') + len('</style>'); style, rest = rest[:e], rest[e:]
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{DESC}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="website">
{pre}{style}
</head>
<body>
{rest}
</body>
</html>
'''


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    doc = wrap(open(src).read())
    open(dst, "w").write(doc)
    print(dst, len(doc.encode()), "bytes")
