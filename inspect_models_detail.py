with open('models.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'khata' in line.lower():
        print(f"{i+1}: {line.strip()}")
