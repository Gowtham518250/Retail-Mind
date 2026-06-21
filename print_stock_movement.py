with open('inventory.py', 'r') as f:
    lines = f.readlines()

start = -1
for i, line in enumerate(lines):
    if '@router.post("/stock-movement"' in line:
        start = i
        break

if start != -1:
    for line in lines[start:start+50]:
        print(line.strip())
