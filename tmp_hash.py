import hashlib
import glob
import os
def hash_files():
    files = glob.glob('data/*.csv') + ['docs/sim_results.json']
    hashes = {}
    for f in sorted(files):
        with open(f, 'rb') as file:
            hashes[f] = hashlib.sha256(file.read()).hexdigest()
        print(f"{f}: {hashes[f]}")
    return hashes

print('--- Run 1 ---')
os.system(r'.venv\Scripts\python.exe ml\build_all.py')
hash1 = hash_files()
print('--- Run 2 ---')
os.system(r'.venv\Scripts\python.exe ml\build_all.py')
hash2 = hash_files()
if hash1 == hash2:
    print('PASS: Hashes identical')
else:
    print('FAIL: Hashes differ')
