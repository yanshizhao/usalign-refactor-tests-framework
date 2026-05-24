#!/usr/bin/env python3
import subprocess, os, sys, re
from pathlib import Path

"""
性能基线生成脚本（Performance Baseline Creator）
功能：
  1. 编译原始版 US-align 可执行文件 (如果尚未编译)
  2. 从 testcases_performance.txt 读取所有性能测试用例
  3. 对每个用例重复运行若干次（默认 5 次），并提取每次的 #Total CPU time
  4. 计算每个用例的平均耗时（秒），保存到 perf_baseline/baseline.csv 中
  5. 提供命令行调试信息（CWD、CMD），并在提取失败时输出警告和程序末尾输出
  6. 自动处理 -dir/-dir2 的路径转换，确保列表文件能被正确找到
注意：该脚本应在修改源代码之前运行一次，以建立性能参考基线。
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"
EXE = "USalign_orig.exe"
PERF_DIR = SCRIPT_DIR / "perf_baseline"
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
    print("Compiling original US-align from master...")
    if subprocess.run(["g++", "-O3", "-ffast-math", "-lm", "-o", EXE, str(SRC)]).returncode != 0:
        print("Compilation failed!"); sys.exit(1)

def extract_time(output: str) -> float:
    m = re.search(r"#Total CPU time\s+is\s+([\d\.]+)\s+seconds", output)
    return float(m.group(1)) if m else 0.0

def run_benchmarks():
    if not PERF_DIR.exists(): PERF_DIR.mkdir(parents=True)
    with open(PERF_DIR / "baseline.csv", "w", newline='') as csv:
        csv.write("case,avg_time\n")
        with open("testcases_performance.txt", "r", encoding="utf-8") as tf:
            for line in tf:
                line = line.strip()
                if not line or line.startswith("#"): continue
                name, workdir_rel, args_str = line.split(maxsplit=2)
                workdir = (DATA_DIR / workdir_rel).resolve()
                args_list = args_str.split()
                cmd = [EXE] + args_list
                print(f"Benchmarking {name} (baseline)...")
                print(f"  CWD: {workdir}")
                print(f"  CMD: {' '.join(cmd)}")
                total = 0.0
                for run_idx in range(RUNS):
                    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
                    t = extract_time(proc.stdout + proc.stderr)
                    if t == 0.0: print(f"  Warning: run {run_idx+1} failed to extract time.")
                    total += t
                avg = round(total / RUNS, 3)
                csv.write(f"{name},{avg}\n")
    print("Performance baseline saved.")

if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for performance baseline...")
            checkout("master")
        compile()
        run_benchmarks()
    finally:
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)