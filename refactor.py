import os
import glob

# Replace current_user and current_user
for file in glob.glob('*.py'):
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'current_user' in content or "current_user" in content:
        new_content = content.replace('current_user', 'current_user').replace("current_user", 'current_user')
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file}")
