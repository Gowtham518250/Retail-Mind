import json

with open('test_report.json', 'r') as f:
    d = json.load(f)

for x in d['results']:
    if x['status'] not in ('PASS', 'SKIP'):
        print(f"=== {x.get('label', 'No Label')} ({x.get('code', 'No Code')}) ===")
        print(f"Details: {x}")
        print("-" * 50)
