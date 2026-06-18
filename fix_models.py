lines = open('models.py', 'r', encoding='utf-8').readlines()
out = []
found_junk = False
for line in lines:
    if line.startswith('Enhanced Database Models'):
        found_junk = True
        break

if found_junk:
    # the junk starts around line 166. We need to find where the original file got truncated.
    # Actually, the junk IS the complete file! 
    # Let's just find the start of the junk and use only the junk (minus the first few lines of the junk block).
    # Wait, the string 'Enhanced Database Models for Hybrid Search RAG' is the very first line of models.py!
    # So if we just find the second occurrence of '"""', or just find 'Enhanced Database Models' and keep everything from its previous line '"""'
    pass

import re
with open('models.py', 'r', encoding='utf-8') as f:
    content = f.read()

# find the last occurrence of 'Enhanced Database Models'
idx = content.rfind('Enhanced Database Models')
if idx != -1:
    # find the '"""' before it
    idx2 = content.rfind('"""\n', 0, idx)
    if idx2 != -1:
        new_content = content[idx2:]
        with open('models.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Fixed models.py!')
