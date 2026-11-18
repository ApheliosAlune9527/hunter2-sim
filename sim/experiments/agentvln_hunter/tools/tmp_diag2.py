
import json
p='/mnt/d/rob-memory/outputs/agentvln_reverse_record_20261110_042000/report.json'
d=json.load(open(p))
L=d['legs']
print('legs type', type(L), len(L))
for i,leg in enumerate(L):
    if isinstance(leg, dict):
        print('== leg', i, 'keys', list(leg))
print('== failed leg detail')
f=L[3]
for k,v in f.items():
    s=json.dumps(v, ensure_ascii=False)
    print(' ', k, ':', (s[:300] + ('...' if len(s)>300 else '')))
