with open('ultra_test_suite.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'khata' in line.lower():
        print(f"{i+1}: {line.strip().encode('ascii', 'replace').decode('ascii')}")
