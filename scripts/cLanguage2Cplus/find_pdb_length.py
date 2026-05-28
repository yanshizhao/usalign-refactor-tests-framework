"""
Scan all PDB files in a specified directory, count amino acid sequence lengths (CA atom count),
sort in descending order by length, and export to an Excel file.
"""

import os
from pathlib import Path
import sys

# ==================== Configuration ====================
PDB_DIR = "../data/PDB/PDB"          # Relative path to PDB folder
OUTPUT_FILE = "../data/PDB/pdb_lengths.xlsx"  # Output Excel file path
MIN_LENGTH = 1500                    # Adjustable filter threshold (for screen highlighting)
# =================================================

def get_chain_length(pdb_path):
    """Count the number of CA atoms (i.e., protein chain length) in a PDB file"""
    try:
        with open(pdb_path, 'r', encoding='utf-8', errors='ignore') as f:
            ca_count = 0
            for line in f:
                if line.startswith("ATOM") and line[12:16].strip() == "CA":
                    ca_count += 1
            return ca_count
    except Exception:
        return 0

def save_to_excel(data, output_path):
    """Save a list of (filename, length) pairs to an Excel file"""
    try:
        from openpyxl import Workbook
    except ImportError:
        print("\nError: openpyxl library not found. Please install it: pip install openpyxl")
        print("The script will output a CSV file instead.")
        csv_path = output_path.replace('.xlsx', '.csv')
        with open(csv_path, 'w', encoding='utf-8-sig') as f:
            f.write("Filename,Length\n")
            for name, length in data:
                f.write(f"{name},{length}\n")
        print(f"Saved as CSV file: {os.path.abspath(csv_path)}")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "PDB Lengths"
    ws.append(["Filename", "Length"])
    for name, length in data:
        ws.append([name, length])
    wb.save(output_path)
    print(f"\nExcel file saved: {os.path.abspath(output_path)}")

def main():
    print(f"Checking directory: {Path(PDB_DIR).absolute()}", flush=True)
    pdb_dir = Path(PDB_DIR)
    if not pdb_dir.exists():
        print(f"Directory does not exist: {pdb_dir.absolute()}")
        return

    files = list(pdb_dir.glob("*.pdb")) + list(pdb_dir.glob("*.pdb1"))
    total = len(files)
    print(f"Found {total} PDB files in total\n", flush=True)

    all_lengths = []   # Store all (filename, length) pairs
    long_count = 0

    for idx, pdb_file in enumerate(files, 1):
        if idx % 100 == 0 or idx == 1:
            print(f"  Scanning progress: {idx}/{total} ...", flush=True)

        length = get_chain_length(pdb_file)
        all_lengths.append((pdb_file.name, length))

        if length >= MIN_LENGTH:
            long_count += 1
            print(f"    -> Found long structure: {pdb_file.name} (length {length})", flush=True)

    # Sort by length in descending order
    all_lengths.sort(key=lambda x: x[1], reverse=True)

    print(f"\nScan complete. {total} files total, {long_count} with length >= {MIN_LENGTH}.")

    # Export to Excel
    save_to_excel(all_lengths, OUTPUT_FILE)

    # Also print the top 20 longest structures on screen
    print("\n========== Top 20 by Length ==========")
    for name, length in all_lengths[:20]:
        print(f"{name:<25s} Length: {length}")

if __name__ == "__main__":
    main()