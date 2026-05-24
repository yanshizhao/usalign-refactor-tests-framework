#!/usr/bin/env python3
import subprocess, os, sys, re, csv
from pathlib import Path

"""
性能回归测试脚本（Performance Regression Runner）
功能：
  1. 切换到 USalign-beta 分支，编译包含需求修改的 US-align 可执行文件
  2. 从 testcases_performance.txt 读取所有性能测试用例
  3. 对每个用例重复运行若干次（默认 5 次），提取平均 CPU 时间
  4. 将结果保存到 perf_current/ 目录下的 performance.csv 中
  5. 读取 perf_baseline/baseline.csv 中的基线数据，与本次结果进行对比
  6. 计算每个用例的时间变化百分比，按阈值分级输出：
       < 20%  : PASS (正常波动)
       20%-50%: WARNING (需关注)
       > 50%  : FAIL (性能显著退化)
  7. 自动处理路径，确保性能测试在正确的目录下执行
注意：修改 US-align 源码后运行此脚本，以评估修改对计算效率的影响。
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"
EXE = SCRIPT_DIR / f"USalign_mod_{os.getpid()}.exe"
BASELINE_CSV = SCRIPT_DIR / "perf_baseline" / "baseline.csv"
CURRENT_DIR = SCRIPT_DIR / "perf_current"
CURRENT_CSV = CURRENT_DIR / "performance.csv"
RUNS = 5

def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def compile():
    print("Compiling modified US-align from USalign-beta...")
    if subprocess.run(["g++", "-O3", "-ffast-math", "-lm", "-o", str(EXE), str(SRC)]).returncode != 0:
        print("Compilation failed!"); sys.exit(1)

def extract_time(output: str) -> float:
    m = re.search(r"#Total CPU time\s+is\s+([\d\.]+)\s+seconds", output)
    return float(m.group(1)) if m else 0.0

def run_benchmarks():
    if not CURRENT_DIR.exists(): CURRENT_DIR.mkdir(parents=True)
    with open(CURRENT_CSV, "w", newline='') as csv_out:
        csv_out.write("case,avg_time\n")
        with open("testcases_performance.txt", "r", encoding="utf-8") as tf:
            for line in tf:
                line = line.strip()
                if not line or line.startswith("#"): continue
                name, workdir_rel, args_str = line.split(maxsplit=2)
                workdir = (DATA_DIR / workdir_rel).resolve()
                args_list = args_str.split()
                cmd = [str(EXE)] + args_list
                print(f"Benchmarking {name} (modified)...")
                print(f"  CWD: {workdir}")
                print(f"  CMD: {' '.join(cmd)}")
                total = 0.0
                for _ in range(RUNS):
                    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
                    total += extract_time(proc.stdout + proc.stderr)
                avg = round(total / RUNS, 3)
                csv_out.write(f"{name},{avg}\n")

def compare():
    if not BASELINE_CSV.exists():
        print("Baseline CSV not found."); return
    with open(BASELINE_CSV, "r", newline='') as f:
        baseline = {row['case']: float(row['avg_time']) for row in csv.DictReader(f)}
    with open(CURRENT_CSV, "r", newline='') as f:
        current  = {row['case']: float(row['avg_time']) for row in csv.DictReader(f)}
    total, passed, warned, failed = 0, 0, 0, 0
    for case, t0 in baseline.items():
        t1 = current.get(case)
        if t1 is None:
            print(f"{case}: MISSING"); total += 1; failed += 1; continue
        pct = (t1 - t0) / t0 * 100
        if pct < 20: status = "PASS"
        elif pct < 50: status = "WARNING"
        else: status = "FAIL"
        if status == "PASS": passed += 1
        elif status == "WARNING": warned += 1
        else: failed += 1
        total += 1
        print(f"{case}: {status} ({pct:+.1f}%)")
    print(f"\n=== Summary: total={total}, PASS={passed}, WARNING={warned}, FAIL={failed} ===")

if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "USalign-beta":
            print(f"Switching USalign from {original_branch} to USalign-beta for performance test...")
            checkout("USalign-beta")
        compile()
        run_benchmarks()
        compare()
    finally:
        if EXE.exists():
            EXE.unlink()
        if original_branch and original_branch != "USalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)