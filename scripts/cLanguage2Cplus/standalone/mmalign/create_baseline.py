#!/usr/bin/env python3
"""
MMalign 基线创建脚本
切换到干净的 master 分支，提取未修改源码编译原始版 MMalign，运行全部用例，输出保存到 baseline/。
脚本结束后恢复运行前所在分支。
"""
import subprocess, os, shutil, sys, tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
USALIGN_DIR  = SCRIPT_DIR / ".." / ".." / ".." / ".." / ".." / "USalign"
DATA_DIR     = SCRIPT_DIR / ".." / ".." / "data"
BASELINE_DIR = SCRIPT_DIR / "baseline"
SRC_MAIN     = "MMalign.cpp"
EXE_NAME     = "MMalign_orig.exe"


def current_branch():
    result = subprocess.run(["git", "branch", "--show-current"], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to get current branch:\n{result.stderr}"); sys.exit(1)
    return result.stdout.strip()


def checkout(branch):
    result = subprocess.run(["git", "checkout", branch], cwd=str(USALIGN_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to checkout {branch}:\n{result.stderr}"); sys.exit(1)


def extract_master_sources(tmpdir: str):
    """从 master 分支提取所有 .cpp .h 源码到临时目录"""
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", "-r", "master"],
        capture_output=True, text=True, cwd=str(USALIGN_DIR)
    )
    if result.returncode != 0:
        print("ERROR: cannot list master branch"); sys.exit(1)

    for fname in result.stdout.strip().split("\n"):
        if not fname.endswith((".cpp", ".h")):
            continue
        content = subprocess.run(
            ["git", "show", f"master:{fname}"],
            capture_output=True, text=True, cwd=str(USALIGN_DIR)
        )
        if content.returncode != 0:
            print(f"WARNING: skip {fname}")
            continue
        dst = os.path.join(tmpdir, fname)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content.stdout)


def compile_orig(exe_path: str, tmpdir: str):
    print("Compiling original MMalign from master ...")
    src = os.path.join(tmpdir, SRC_MAIN)
    r = subprocess.run(
        ["g++", "-O3", "-ffast-math", "-lm", "-static", "-o", exe_path, src],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print("Compilation FAILED:\n" + r.stderr); sys.exit(1)
    print("Compilation OK.")


def run_baseline(exe_path: str):
    if BASELINE_DIR.exists():
        shutil.rmtree(BASELINE_DIR)
    BASELINE_DIR.mkdir(parents=True)

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

            print(f"=== {name} ===")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr

            out_file = BASELINE_DIR / f"{name}.out"
            out_file.write_text(content, encoding="utf-8")

            # MMalign -o complex1.sup 会生成 complex1.sup 和 complex1.sup.pml
            sup_file = workdir / "complex1.sup"
            if sup_file.exists():
                shutil.move(str(sup_file), str(BASELINE_DIR / f"{name}.sup"))

            # MMalign -m matrix.txt 会生成矩阵文件
            matrix_file = workdir / "matrix.txt"
            if matrix_file.exists():
                shutil.move(str(matrix_file), str(BASELINE_DIR / f"{name}.matrix.txt"))

            # 清理 .pml 文件（不参与比对）
            for pml in workdir.glob("*.pml"):
                pml.unlink()

    print("\nMMalign baseline created.")


if __name__ == "__main__":
    original_branch = current_branch()
    tmpdir = tempfile.mkdtemp(prefix="mmalign_orig_")
    try:
        if original_branch != "master":
            print(f"Switching USalign from {original_branch} to master for MMalign baseline...")
            checkout("master")
        extract_master_sources(tmpdir)
        exe = str(SCRIPT_DIR / EXE_NAME)
        compile_orig(exe, tmpdir)
        run_baseline(exe)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if original_branch and original_branch != "master":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)
