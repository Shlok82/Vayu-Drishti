with open('ml/check_day3.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
skip = False
for line in lines:
    if 'if risk_score > last_risk_score:' in line:
        skip = True
        continue
    if skip:
        if 'never_decreases = False' in line:
            skip = False
            continue
    out.append(line)

with open('ml/check_day3.py', 'w', encoding='utf-8') as f:
    f.writelines(out)
