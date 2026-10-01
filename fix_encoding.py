import os
import re

def fix_encoding():
    # Use hex escapes to avoid having the characters in this file
    mojibake_pattern = re.compile('[\u00e2\u00f0\u00c3\u00c2\u00ef\u00b8\ufffd]')
    
    hits = []
    
    for root, dirs, files in os.walk('.'):
        if '.venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if not file.endswith(('.py', '.md', '.csv', '.toml', '.json')):
                continue
                
            path = os.path.join(root, file)
            if 'fix_encoding.py' in path:
                continue
            
            # Check BOM
            with open(path, 'rb') as f:
                raw = f.read()
                has_bom = raw.startswith(b'\xef\xbb\xbf')
                
            if has_bom:
                raw = raw[3:]
                with open(path, 'wb') as f:
                    f.write(raw)
                hits.append(f"BOM removed in {path}")
                
            # Check content
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                continue
                
            changed = False
            for i, line in enumerate(lines):
                orig = line
                    
                # Search mojibake
                if mojibake_pattern.search(line):
                    hits.append(f"{path}:{i+1} -> Mojibake found")
                    # Replace specific known corrupted sequences if present
                    line = line.replace('\u00e2\u0161\u0020\u00ef\u00b8\u008f', '[WARN]')
                    line = line.replace('\u00f0\u0178\u0161\u00a8', '[CRITICAL]')
                    line = line.replace('\u00e2\u0153\u2026', '[OK]')
                    line = line.replace('\u00e2\u201e\u00b9\u00ef\u00b8\u008f', '[INFO]')
                    line = line.replace('\u00f0\u0178\u0178\u00a2', 'GREEN')
                    line = line.replace('\u00f0\u0178\u0178\u00a1', 'AMBER')
                    line = line.replace('\u00f0\u0178\u201d\u00b4', 'RED')
                    # Strip leftovers
                    line = mojibake_pattern.sub('', line)
                    
                if line != orig:
                    lines[i] = line
                    changed = True
                    
            if changed:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                    
    with open('encoding_hits.txt', 'w', encoding='utf-8') as f:
        for h in hits:
            f.write(h + '\n')
    print("Done checking encoding. See encoding_hits.txt")

fix_encoding()
