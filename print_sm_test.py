with open('ultra_test_suite.py', 'r', encoding='utf-8') as f:
    text = f.read()

# search for /stock-movement
lines = text.split('\n')
for i, line in enumerate(lines):
    if '/stock-movement' in line:
        for idx in range(i, i+15):
            print(lines[idx])
