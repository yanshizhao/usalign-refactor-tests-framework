#!/usr/bin/env python3
import subprocess, os, sys, shutil, difflib, re
from pathlib import Path


"""
回归测试执行脚本（Regression Runner）
功能：
  1. 切换到 Usalign-beta 分支，编译包含需求修改的 US-align 可执行文件 (USalign_mod.exe)
  2. 每次运行前自动清空 current/ 和 diffs/ 目录，避免旧数据干扰
  3. 从 testcases_functional.txt 读取所有功能测试用例
  4. 逐条运行用例，将输出保存到 current/ 目录（文件名添加 _mod 后缀）
  5. 将修改版输出与 baseline/ 中的原始基线进行逐字节比较
  6. 若完全一致，报告 “PASS”；若不一致，报告 “CHECK” 并在 diffs/ 目录中
     生成详细的 unified diff 文件，便于人工审查差异点
  7. 支持叠加结构 (superposed_structure) 的特殊处理，自动移动和清洗 .pml 文件
注意：修改 US-align 源码后运行此脚本，以验证修改未引入功能回归。
"""

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / "data"
CURRENT = SCRIPT_DIR / "current"
DIFFS   = SCRIPT_DIR / "diffs"
BASELINE= SCRIPT_DIR / "baseline"
USALIGN_DIR = (SCRIPT_DIR / ".." / ".." / ".." / "USalign").resolve()
SRC = USALIGN_DIR / "USalign.cpp"
EXE = SCRIPT_DIR / f"USalign_mod_{os.getpid()}.exe"
MOD_SUFFIX = "_mod"


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
    print("Compiling modified US-align from Usalign-beta...")
    if subprocess.run(["g++", "-O3", "-ffast-math", "-lm", "-o", str(EXE), str(SRC)]).returncode != 0:
        print("Compilation failed!"); sys.exit(1)


def clean_directory(dir_path):
    if dir_path.exists():
        shutil.rmtree(dir_path, ignore_errors=True)
    dir_path.mkdir(parents=True, exist_ok=True)


def clean_slash(text: str) -> str:
    """移除输出中 Name of Structure_X: 后面多余的 '/' 前缀"""
    return re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', text)


def run_tests():
    clean_directory(CURRENT)
    clean_directory(DIFFS)

    total, passed, checked, failed = 0, 0, 0, 0

    with open("testcases_functional.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, workdir_rel, args_str = line.split(maxsplit=2)
            workdir = (DATA_DIR / workdir_rel).resolve()
            args_list = args_str.split()
            cmd = [str(EXE)] + args_list
            print(f"Running {name} ...")
            print(f"  CWD: {workdir}")
            print(f"  CMD: {' '.join(cmd)}")

            # 捕获输出，清洗后写入文件
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))
            content = proc.stdout + proc.stderr
            content = clean_slash(content)

            out_filename = f"{name}{MOD_SUFFIX}.out"
            out_file = CURRENT / out_filename
            with open(out_file, "w", encoding="utf-8") as of:
                of.write(content)

            if name == "superposed_structure":
                total += 1
                sup_pdb = workdir / "sup.pdb"
                if sup_pdb.exists():
                    shutil.move(str(sup_pdb), str(CURRENT / f"sup{MOD_SUFFIX}.pdb"))
                for pml in workdir.glob("*.pml"):
                    pml.unlink()
                result = _diff_files("sup.pdb", f"sup{MOD_SUFFIX}.pdb", name, " (structure)")
                if result == "PASS":
                    passed += 1
                elif result == "CHECK":
                    checked += 1
                else:
                    failed += 1
            else:
                total += 1
                result = _diff_files(f"{name}.out", out_filename, name)
                if result == "PASS":
                    passed += 1
                elif result == "CHECK":
                    checked += 1
                else:
                    failed += 1

    print(f"\n=== Summary: total={total}, PASS={passed}, CHECK={checked}, FAIL={failed} ===")


def _diff_files(base_filename, mod_filename, tag, extra_note=""):
    base = BASELINE / base_filename
    curr = CURRENT / mod_filename
    diff = DIFFS / f"{tag}.diff"
    try:
        with open(base, "rb") as fb, open(curr, "rb") as fc:
            bdata = fb.read()
            cdata = fc.read()
        if bdata == cdata:
            print(f"  PASS{extra_note}")
            if diff.exists():
                diff.unlink()
            return "PASS"
        else:
            print(f"  CHECK{extra_note} (see {diff})")
            blines = bdata.decode('utf-8', errors='replace').splitlines(keepends=True)
            clines = cdata.decode('utf-8', errors='replace').splitlines(keepends=True)
            diff_content = difflib.unified_diff(
                blines, clines, fromfile=str(base), tofile=str(curr)
            )
            with open(diff, "w", encoding="utf-8") as df:
                df.writelines(diff_content)
            return "CHECK"
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return "ERROR"


if __name__ == "__main__":
    original_branch = current_branch()
    try:
        if original_branch != "Usalign-beta":
            print(f"Switching USalign from {original_branch} to Usalign-beta for functional regression...")
            checkout("Usalign-beta")
        compile()
        run_tests()
    finally:
        if EXE.exists():
            EXE.unlink()
        if original_branch and original_branch != "Usalign-beta":
            print(f"Restoring USalign branch to {original_branch}...")
            checkout(original_branch)