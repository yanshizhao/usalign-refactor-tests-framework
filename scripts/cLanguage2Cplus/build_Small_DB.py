"""
Build smallDB by randomly sampling PDB files from an I-TASSER template library.
Cross-platform (Windows / Linux / macOS).

Usage:
    1. Place this script in the scripts/cLanguage2Cplus/ directory
    2. Modify SOURCE_DIR below to your I-TASSER library extraction path
    3. Run from the command line: python build_Small_DB.py
"""

import os
import random
import shutil
import sys

# ==================== Configuration ====================
# Modify to your actual I-TASSER library extraction path (directory containing .pdb files).
# Example Windows: r"D:\I-TASSER\template\pdb"
# Example Linux:   "/home/user/I-TASSER/template/pdb"
SOURCE_DIR = "/path/to/I-TASSER/template/pdb"

# The target directory is inferred automatically by the script; no modification needed
NUM_STRUCTURES = 100
# =================================================


def main():
    # 1. Automatically determine the cLanguage2Cplus test directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "data", "smallDB")

    print(f"Script location: {script_dir}")
    print(f"Target directory: {target_dir}")

    # 2. Check the source directory
    if not os.path.isdir(SOURCE_DIR):
        print(f"Error: source directory does not exist: {SOURCE_DIR}")
        print("Please modify SOURCE_DIR in the script to the actual I-TASSER library extraction path.")
        return 1

    # 3. Clean and create the target directory (clear all contents in smallDB before each run)
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            print(f"Cleared existing directory: {target_dir}")
        except Exception as e:
            print(f"Error: could not clear target directory {target_dir} - {e}")
            return 1
    os.makedirs(target_dir, exist_ok=True)
    print(f"Target directory ready: {target_dir}")

    # 4. Get all PDB files from the source directory
    pdb_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.pdb')]
    print(f"Found {len(pdb_files)} PDB files in the source directory.")

    if len(pdb_files) == 0:
        print("Error: no .pdb files found in the source directory. Please check the path.")
        return 1

    # 5. Random sampling (select all if fewer than the desired count)
    random.seed(42)   # Fixed seed for reproducibility
    if len(pdb_files) >= NUM_STRUCTURES:
        selected_files = random.sample(pdb_files, NUM_STRUCTURES)
    else:
        selected_files = pdb_files
        print(f"Warning: source directory has fewer than {NUM_STRUCTURES} files; all will be copied.")

    # 6. Copy files
    success = 0
    for f in selected_files:
        src = os.path.join(SOURCE_DIR, f)
        dst = os.path.join(target_dir, f)
        try:
            shutil.copy2(src, dst)   # copy2 preserves original file timestamps, etc.
            success += 1
        except Exception as e:
            print(f"Failed to copy: {f} - {e}")

    print(f"Successfully copied {success} PDB files to the target directory.")

    # 7. Generate list file (one PDB ID per line, no extension)
    list_path = os.path.join(target_dir, "list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for pdb_file in selected_files:
            pdb_id = os.path.splitext(pdb_file)[0]   # Strip .pdb extension
            f.write(pdb_id + "\n")
    print(f"list.txt file generated: {list_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nUser interrupted the operation")
        sys.exit(1)
    except Exception as e:
        print(f"Program exception: {e}")
        sys.exit(1)