with open('inventory.py', 'r') as f:
    text = f.read()

# find def containing stock_movement or routes
for line in text.split('\n'):
    if 'stock-movement' in line or 'stock_movement' in line:
        print(line)
