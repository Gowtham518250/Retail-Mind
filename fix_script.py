import re
with open('ultra_test_suite.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Find the missing definition section using a regex that matches the header line and everything after it
match = re.search(r'(# .*31. ADDITIONAL MISSING ENDPOINTS.*)', text, re.DOTALL)
if match:
    missing_text = match.group(1)
    text = text.replace(missing_text, '')
    
    # insert before __main__
    main_match = re.search(r'if __name__ == "__main__":', text)
    if main_match:
        text = text[:main_match.start()] + missing_text + '\n\n' + text[main_match.start():]
        with open('ultra_test_suite.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print('Fixed!')
    else:
        print('no main')
else:
    print('no match')
