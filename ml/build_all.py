import sys
import subprocess
from pathlib import Path

_root = Path(__file__).resolve().parents[1]

def run_script(name):
    print(f"--- Running {name} ---")
    res = subprocess.run([sys.executable, str(_root / 'ml' / name)], cwd=str(_root))
    if res.returncode != 0:
        print(f"ERROR: {name} failed with exit code {res.returncode}")
        sys.exit(res.returncode)

if __name__ == '__main__':
    run_script('make_synthetic.py')
    run_script('make_predictions.py')
    run_script('evaluate.py')
    run_script('precompute.py')
    run_script('simulate_policies.py')
    print("build_all completed successfully.")
