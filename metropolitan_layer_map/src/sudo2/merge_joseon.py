import json
P='/home/claude/sudo/page/data.json'
d=json.load(open(P)); j=json.load(open('/home/claude/sudo2/joseon_sudo.json'))
d['joseon']=j
json.dump(d,open(P,'w'),ensure_ascii=False,separators=(',',':'))
print(len(j['roads']),len(j['pts']))
