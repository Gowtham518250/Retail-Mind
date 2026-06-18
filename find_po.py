import json
import re

transcript_path = r'C:\Users\vanam\.gemini\antigravity\brain\52138620-a929-4339-8812-e3ee08020703\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    data = json.loads(line)
    content = data.get('content', '')
    if 'class PurchaseOrder(Base):' in content:
        print("FOUND! Extracted from content:")
        # Find where it starts and print 5000 characters
        idx = content.find('class PurchaseOrder(Base):')
        print(content[max(0, idx-500):idx+3000])
        break
    elif 'output' in content and 'purchase_orders' in content:
        # Check inside dict if it's a string representation
        pass
