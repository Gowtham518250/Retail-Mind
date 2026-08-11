with open('inventory.py', 'r') as f:
    text = f.read()

# Print class StockMovementCreate definition
lines = text.split('\n')
start = -1
for i, line in enumerate(lines):
    if 'class StockMovementCreate' in line:
        start = i
        break

if start != -1:
    for line in lines[start:start+15]:
        print(line)
