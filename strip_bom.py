import os
def strip_bom():
    changed = []
    for root, dirs, files in os.walk('.'):
        if '.git' in root or '.venv' in root or '__pycache__' in root:
            continue
        for f in files:
            if not f.endswith(('.py', '.md', '.csv', '.json', '.toml')): continue
            path = os.path.join(root, f)
            try:
                with open(path, 'rb') as f_in:
                    content = f_in.read()
                if content.startswith(b'\xef\xbb\xbf'):
                    with open(path, 'wb') as f_out:
                        f_out.write(content[3:])
                    changed.append(path)
            except Exception as e:
                pass
    print("Stripped BOM from:", changed)
strip_bom()
