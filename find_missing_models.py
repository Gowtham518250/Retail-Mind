import os
import re
import glob

# Get all models defined in models.py
with open('models.py', 'r', encoding='utf-8') as f:
    models_content = f.read()

defined_models = set(re.findall(r'class ([A-Za-z0-9_]+)\(Base\):', models_content))

imported_models = set()
for file in glob.glob('*.py'):
    if file == 'models.py': continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find from models import X, Y, Z
    for match in re.finditer(r'from models import ([A-Za-z0-9_,\s]+)', content):
        imports = match.group(1).split(',')
        for imp in imports:
            imp = imp.strip()
            if imp and imp != 'Base':
                imported_models.add(imp)

missing_models = imported_models - defined_models
print("Missing models:", missing_models)
