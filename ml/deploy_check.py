import os
import sys
import time
import shutil
import tempfile
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    repo_dir = Path(__file__).resolve().parents[1]
    total_start = time.time()
    
    # Global log file in system temp folder
    log_file_path = Path(tempfile.gettempdir()) / f"deploy_check_{int(time.time())}.log"
    log_fp = open(log_file_path, "a", encoding="utf-8")

    def log(msg):
        ts_msg = f"[{get_timestamp()}] {msg}"
        print(ts_msg, flush=True)
        log_fp.write(ts_msg + "\n")
        log_fp.flush()

    def print_last_lines(file_path, n=40):
        if not file_path or not Path(file_path).exists():
            return
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-n:]
            log(f"--- Last {len(tail)} lines of {Path(file_path).name} ---")
            for line in tail:
                print("  " + line.rstrip(), flush=True)
                log_fp.write("  " + line.rstrip() + "\n")
            log_fp.flush()
        except Exception as e:
            log(f"Could not read tail of {file_path}: {e}")

    log("=== Vayu Drishti Deployment Check (Hardened) ===")
    log(f"Base Repository: {repo_dir}")
    log(f"Log File: {log_file_path}")
    log(f"Host Python: {sys.version.split()[0]} ({sys.executable})")

    # Check for untracked non-ignored files
    res_untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True
    )
    untracked_files = [line.strip() for line in res_untracked.stdout.splitlines() if line.strip()]
    if untracked_files:
        log(f"[WARN] Untracked non-ignored files found ({len(untracked_files)}): {untracked_files}")
    else:
        log("[INFO] No untracked non-ignored files present.")

    # Step 1: Collect files via git ls-files
    log("[STEP 1 START] Collecting deployment files via git ls-files")
    t0 = time.time()
    res = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True,
        timeout=60
    )
    all_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    deploy_files = [
        f for f in all_files 
        if not f.startswith("data/raw") 
        and not f.startswith(".venv") 
        and not f.startswith(".git")
    ]
    t_gather = time.time() - t0
    log(f"[STEP 1 END] Collected {len(deploy_files)} deployment files ({t_gather:.2f}s)")

    temp_dir = Path(tempfile.mkdtemp(prefix="vayudrishti_deploy_"))
    log(f"Deployment Sandbox: {temp_dir}")

    step_log_path = Path(tempfile.gettempdir()) / f"deploy_step_{int(time.time())}.log"

    try:
        # Step 2: Copy files
        log("[STEP 2 START] Copying files to sandbox (timeout: 60s)")
        t0 = time.time()
        for rel_f in deploy_files:
            src = repo_dir / rel_f
            if src.is_file():
                dest = temp_dir / rel_f
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        t_copy = time.time() - t0
        log(f"[STEP 2 END] Files copied successfully ({t_copy:.2f}s)")

        # Step 3: Create venv
        log("[STEP 3 START] Creating clean virtual environment (timeout: 120s)")
        t0 = time.time()
        venv_dir = temp_dir / ".venv"
        with open(step_log_path, "w", encoding="utf-8") as step_fp:
            try:
                subprocess.run(
                    [sys.executable, "-m", "venv", str(venv_dir)],
                    cwd=str(temp_dir),
                    stdout=step_fp,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=120
                )
            except Exception as e:
                log(f"[FAILED] venv creation failed: {e}")
                print_last_lines(step_log_path)
                sys.exit(1)

        if os.name == 'nt':
            venv_py = venv_dir / "Scripts" / "python.exe"
            venv_pip = venv_dir / "Scripts" / "pip.exe"
        else:
            venv_py = venv_dir / "bin" / "python"
            venv_pip = venv_dir / "bin" / "pip"

        # Print venv's python and pip versions
        v_py = subprocess.run([str(venv_py), "--version"], capture_output=True, text=True).stdout.strip()
        v_pip = subprocess.run([str(venv_pip), "--version"], capture_output=True, text=True).stdout.strip()
        t_venv = time.time() - t0
        log(f"   Venv Python: {v_py}")
        log(f"   Venv Pip:    {v_pip}")
        log(f"[STEP 3 END] Virtual environment created ({t_venv:.2f}s)")

        # Step 4: pip install -r requirements.txt ONLY
        log("[STEP 4 START] Running pip install -r requirements.txt ONLY (timeout: 900s)")
        t0 = time.time()
        pip_cmd = [
            str(venv_pip), "install",
            "--disable-pip-version-check",
            "--progress-bar", "off",
            "--only-binary=:all:",
            "-r", "requirements.txt"
        ]
        with open(step_log_path, "w", encoding="utf-8") as step_fp:
            try:
                subprocess.run(
                    pip_cmd,
                    cwd=str(temp_dir),
                    stdout=step_fp,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=900
                )
            except subprocess.CalledProcessError as e:
                log(f"[FAILED] pip install failed with exit code {e.returncode}")
                print_last_lines(step_log_path)
                sys.exit(1)
            except subprocess.TimeoutExpired:
                log("[FAILED] pip install timed out after 900s")
                print_last_lines(step_log_path)
                sys.exit(1)
        t_pip = time.time() - t0
        log(f"[STEP 4 END] pip install completed successfully ({t_pip:.2f}s)")

        # Clean environment without PYTHONPATH
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)

        # Step 5: Run check_day1, check_day2, check_day3
        for chk in ["check_day1.py", "check_day2.py", "check_day3.py"]:
            log(f"[STEP 5 START] Running ml/{chk} (timeout: 300s)")
            t0 = time.time()
            with open(step_log_path, "w", encoding="utf-8") as step_fp:
                try:
                    subprocess.run(
                        [str(venv_py), f"ml/{chk}"],
                        cwd=str(temp_dir),
                        env=clean_env,
                        stdout=step_fp,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=300
                    )
                except subprocess.CalledProcessError as e:
                    log(f"[FAILED] {chk} failed with exit code {e.returncode}")
                    print_last_lines(step_log_path)
                    sys.exit(1)
                except subprocess.TimeoutExpired:
                    log(f"[FAILED] {chk} timed out after 300s")
                    print_last_lines(step_log_path)
                    sys.exit(1)
            t_chk = time.time() - t0
            # Read last summary line
            with open(step_log_path, "r", encoding="utf-8", errors="replace") as f:
                chk_lines = f.readlines()
            summary_candidates = [l.strip() for l in chk_lines if "passed" in l.lower()]
            summary = summary_candidates[-1] if summary_candidates else "OK"
            log(f"[STEP 5 END] ml/{chk}: PASS ({summary}) ({t_chk:.2f}s)")

        # Step 6: AppTest on each page
        pages = [
            "app/main.py",
            "app/pages/0_Fleet_Overview.py",
            "app/pages/1_Aircraft_Detail.py",
            "app/pages/2_Digital_Twin.py",
            "app/pages/3_Planner.py",
            "app/pages/4_Results.py",
            "app/pages/5_Method.py"
        ]
        for page_rel in pages:
            page_name = Path(page_rel).name
            log(f"[STEP 6 START] Running AppTest on {page_name} (timeout: 60s)")
            t0 = time.time()
            apptest_snippet = f"""
import sys
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(r"{page_rel}", default_timeout=30)
at.run()
if at.exception:
    print(f"EXCEPTION: {{at.exception}}")
    sys.exit(1)
print("PASS")
"""
            with open(step_log_path, "w", encoding="utf-8") as step_fp:
                try:
                    subprocess.run(
                        [str(venv_py), "-c", apptest_snippet],
                        cwd=str(temp_dir),
                        env=clean_env,
                        stdout=step_fp,
                        stderr=subprocess.STDOUT,
                        check=True,
                        timeout=60
                    )
                except subprocess.CalledProcessError as e:
                    log(f"[FAILED] AppTest failed for {page_name} (exit code {e.returncode})")
                    print_last_lines(step_log_path)
                    sys.exit(1)
                except subprocess.TimeoutExpired:
                    log(f"[FAILED] AppTest timed out for {page_name}")
                    print_last_lines(step_log_path)
                    sys.exit(1)
            t_page = time.time() - t0
            log(f"[STEP 6 END] AppTest {page_name}: PASS ({t_page:.2f}s)")

        # Step 7: Streamlit server run and health check
        log("[STEP 7 START] Launching Streamlit server on port 8599 (health timeout: 90s)")
        t0 = time.time()
        port = 8599
        server_log_path = Path(tempfile.gettempdir()) / f"streamlit_server_{int(time.time())}.log"
        server_log_fp = open(server_log_path, "w", encoding="utf-8")
        
        st_cmd = [
            str(venv_py), "-m", "streamlit", "run", "app/main.py",
            "--server.headless", "true",
            "--server.port", str(port),
            "--browser.gatherUsageStats", "false"
        ]
        
        st_proc = subprocess.Popen(
            st_cmd,
            cwd=str(temp_dir),
            env=clean_env,
            stdout=server_log_fp,
            stderr=subprocess.STDOUT
        )
        st_pid = st_proc.pid
        log(f"   Streamlit PID: {st_pid} (server log: {server_log_path})")

        health_url = f"http://localhost:{port}/_stcore/health"
        health_ok = False
        poll_start = time.time()
        timeout_sec = 90

        try:
            while time.time() - poll_start < timeout_sec:
                if st_proc.poll() is not None:
                    log("[FAILED] Streamlit process exited unexpectedly before health check succeeded.")
                    server_log_fp.flush()
                    print_last_lines(server_log_path)
                    sys.exit(1)
                try:
                    with urllib.request.urlopen(health_url, timeout=2) as resp:
                        if resp.status == 200:
                            body = resp.read().decode("utf-8").strip()
                            if body.lower() == "ok":
                                health_ok = True
                                break
                except Exception:
                    time.sleep(2)
        finally:
            # Stop exactly the process and its children
            log(f"   Stopping Streamlit process tree (PID {st_pid})...")
            if os.name == 'nt':
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(st_pid)], capture_output=True)
            else:
                st_proc.terminate()
                try:
                    st_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    st_proc.kill()
            try:
                server_log_fp.close()
            except Exception:
                pass
            
            # Confirm port 8599 is free
            time.sleep(1)
            port_check = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            ).stdout
            port_busy = any(f":{port} " in l for l in port_check.splitlines())
            if port_busy:
                log(f"[WARN] Port {port} still appears in netstat after stopping process.")
            else:
                log(f"   Confirmed port {port} is completely free.")

        t_health = time.time() - t0
        if not health_ok:
            log(f"[FAILED] Health check timed out after {timeout_sec}s")
            print_last_lines(server_log_path)
            sys.exit(1)
        else:
            log(f"[STEP 7 END] Streamlit health check passed (status 200 OK) ({t_health:.2f}s)")

    finally:
        # Step 8: Sandbox cleanup
        log("Cleaning up sandbox...")
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            if step_log_path.exists():
                step_log_path.unlink()
        except Exception:
            pass

    total_time = time.time() - total_start
    log(f"\nDEPLOY CHECK PASSED COMPLETELY! Total time: {total_time:.2f}s")
    log_fp.close()

if __name__ == '__main__':
    main()
