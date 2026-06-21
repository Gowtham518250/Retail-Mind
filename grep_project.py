import os

search_term = "khata_transaction_type"
print(f"Searching for '{search_term}'...")

for root, dirs, files in os.walk('.'):
    # Exclude directories
    if any(p in root for p in ['.git', '__pycache__', 'node_modules', '.agents', '.gemini']):
        continue
    for file in files:
        if file.endswith('.py') or file.endswith('.sql'):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if search_term in content:
                    print(f"Found in {path}")
            except Exception as e:
                pass
