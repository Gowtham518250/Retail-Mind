import json
import re

transcript_path = r'C:\Users\vanam\.gemini\antigravity\brain\52138620-a929-4339-8812-e3ee08020703\.system_generated\logs\transcript_full.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    data = json.loads(line)
    if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
        # Check if this was the tool call where I printed models.py
        # Actually it's in the tool response!
        pass

# It's easier to just find the tool response that has the full models.py
for line in reversed(lines):
    data = json.loads(line)
    if 'output' in data.get('content', ''):
        content = data['content']
        if 'class PurchaseOrder(Base):' in content and '__tablename__ = "purchase_orders"' in content:
            # Extract the output
            start_idx = content.find('class User(Base):')
            end_idx = content.find('# ==================== END OF MODELS ====================')
            if start_idx != -1 and end_idx != -1:
                models_content = content[start_idx:end_idx + 50]
                with open('models_recovered.py', 'w', encoding='utf-8') as mf:
                    mf.write('from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, Numeric, Date, Enum, UniqueConstraint\n')
                    mf.write('from sqlalchemy.orm import relationship\n')
                    mf.write('from sqlalchemy.sql import func\n')
                    mf.write('from datetime import datetime, date\n')
                    mf.write('import enum\n')
                    mf.write('from db import Base\n\n')
                    mf.write(models_content)
                print("Recovered models.py successfully!")
                break
