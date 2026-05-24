#!/usr/bin/env python3
"""
TMscore 回归测试脚本
切换到 Usalign-beta 分支，编译包含需求修改的 TMscore，运行全部用例，与 baseline/ 逐字节比对。
生成文件: -o TM_sup 会产生 TM_sup.pdb / TM_sup.pdb1 / *.pml（pml 不比对）。脚本结束后恢复运行前所在分支。
"""
import subprocess, shutil, sys, difflib, re
from pathlib import Path


def strip_cpu_time(text: str) -> str:
    """移除 #Total CPU time 行 — CPU 时间自然波动，不作为回归判定依据"""
    return re.sub(r'^#Total CPU time.*\n?', '', text, flags=re.MULTILINE)

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
CURRENT_DIR  = SCRIPT_DIR / "current"
DIFFS_DIR    = SCRIPT_DIR / "diffs"
SRC_MAIN     = USALIGN_DIR / "TMscore.cpp"
EXE_NAME     = "TMscore_mod.exe"


def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def compile_mod(exe_path: str):
    print("Compiling modified TMscore ...")
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static", "-o", exe_path, str(SRC_MAIN)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def run_tests(exe_path: str):
    for d in [CURRENT_DIR, DIFFS_DIR]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    if not BASELINE_DIR.exists():
        print("ERROR: baseline/ not found. Run create_baseline.py first."); sys.exit(1)

    total_pass, total_fail = 0, 0
    testcases = SCRIPT_DIR / "testcases.txt"

    with open(testcases, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args = args_str.split()
            cmd = [exe_path] + args

            print(f"=== {name} ===", end=" ")

            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr

            cur_file = CURRENT_DIR / f"{name}.out"
            cur_file.write_text(content, encoding="utf-8")

            base_file = BASELINE_DIR / f"{name}.out"
            if not base_file.exists():
                print("FAIL (no baseline)")
                total_fail += 1
                continue

            base_content = base_file.read_text(encoding="utf-8")

            content = strip_cpu_time(content)
            base_content = strip_cpu_time(base_content)

            if content == base_content:
                print("PASS")
                total_pass += 1
            else:
                print("FAIL")
                total_fail += 1
                diff_file = DIFFS_DIR / f"{name}.diff"
                with open(diff_file, "w", encoding="utf-8") as df:
                    df.writelines(difflib.unified_diff(
                        base_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"baseline/{name}.out",
                        tofile=f"current/{name}.out"))

            # 比对 -o TM_sup 生成的叠合结构文件
            for suffix in [".pdb", ".pdb1"]:
                gen_name = f"TM_sup{suffix}"
                gen_path = workdir / gen_name
                base_gen = BASELINE_DIR / f"{name}{suffix}"
                if gen_path.exists():
                    shutil.copy2(str(gen_path), str(CURRENT_DIR / f"{name}{suffix}"))
                if gen_path.exists() and base_gen.exists():
                    if gen_path.read_bytes() == base_gen.read_bytes():
                        print(f"  {gen_name}: PASS")
                        total_pass += 1
                    else:
                        print(f"  {gen_name}: FAIL")
                        total_fail += 1
                    gen_path.unlink()
                elif gen_path.exists():
                    gen_path.unlink()

            # 清理 pml
            for pml in workdir.glob("*.pml"):
                pml.unlink()

    print(f"\nResults: {total_pass} PASS, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "Usalign-beta":
            print(f"Switching USalign from {original_branch} to Usalign-beta for TMscore regression...")
            checkout("Usalign-beta")
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_mod(exe)
        ok = run_tests(exe)
    finally:
        if original_branch and original_branch != "Usalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
    sys.exit(0 if ok else 1)
