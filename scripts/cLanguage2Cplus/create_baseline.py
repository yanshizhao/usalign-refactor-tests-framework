#!/usr/bin/env python3
import subprocess, os, shutil, sys, re
from pathlib import Path

"""
创建基线文件脚本（Baseline Creator）
功能：
  1. 编译原始（未修改）版本的 US-align 可执行文件 (USalign_orig.exe)
  2. 从 testcases_functional.txt 读取所有功能测试用例
  3. 依次执行每个用例，并将完整的输出（stdout 和 stderr）保存到
     baseline/ 目录下，作为后续回归测试的“黄金标准”
  4. 自动为每个用例设置正确的工作目录，确保所有结构文件能被找到
  5. 对包含 -dir/-dir2 选项的用例，自动将列表文件路径转换为绝对路径
  6. 运行完成后打印 “Baseline created.” 提示
注意：该脚本只应在修改源代码之前运行一次，以建立不可变的预期输出。
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
BASELINE = SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"
EXE = "USalign_orig.exe"


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


def clean_slash(text: str) -> str:
    """移除输出中 Name of Structure_X: 后面多余的 '/' 前缀"""
    return re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)


def run_baseline():
    if not BASELINE.exists():
        BASELINE.mkdir(parents=True)
    with open("testcases_functional.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split()
            cmd = [EXE] + args_list
            print(f"=== {name} ===")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            # 捕获输出，清洗后写入基线文件
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr
            content = clean_slash(content)

            out_file = BASELINE / f"{name}.out"
            with open(out_file, "w", encoding="utf-8") as out:
                out.write(content)

            if name == "superposed_structure":
                sup_pdb = workdir / "sup.pdb"
                if sup_pdb.exists():
                    shutil.move(str(sup_pdb), str(BASELINE / "sup.pdb"))
    print("\nBaseline created.")


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for functional baseline...")
            checkout("master")
        compile()
        run_baseline()
    finally:
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)