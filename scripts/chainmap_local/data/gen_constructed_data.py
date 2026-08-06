#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate test data for -chainmap local-constraint feature tests.

Products (all written to the directory of this script):
  complexA.pdb          complex A: 1c25/1e0ca1/1e0ca2 -> chain A/B/C
  complexB.pdb          complex B: 1qb0a/1rhs1/1rhs2  -> chain A/B/C
  complexB_2chain.pdb   chain-number-mismatch variant (only 2 chains)
  short.pdb             2-residue chain (too-short test)
  map_full.txt          full mapping A->A, B->B, C->C
  map_A.txt             partial mapping A->A (1 pair)
  map_AB.txt            partial mapping A->A, B->B (2 pairs)
  map_swap.txt          crossed mapping A->B, B->A (lock-conflict test)
  map_dup.txt           duplicate target A->A, C->A (defense test)
  map_dup1.txt          duplicate chain1 A->A, A->B (warning test)
  map_nonexist.txt      nonexistent chain X->A (Cannot map test)

Source: HOMSTRAD family Rhodanese
  D:\\qlab\\data\\homstrad\\homstrad\\Rhodanese
Expected standard answer (TM4 from pairwise scores):
  A->A: 1c25 <-> 1qb0a  (0.996)
  B->B: 1e0ca1 <-> 1rhs1 (0.748)
  C->C: 1e0ca2 <-> 1rhs2 (0.757)
"""

import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HOMSTRAD_RHODANESE = r"D:\qlab\data\homstrad\homstrad\Rhodanese"
# 4iaj/4jhm multimer data source (copied locally so test output shows bare filenames)
CLANGUAGE2CPLUS_DATA = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "..", "cLanguage2Cplus", "data"))

# ---- PDB ATOM line rewriting ----
def rewrite_atom(line, atom_serial, chain_id, resi_no):
    """Rewrite atom serial (cols 7-11), chain ID (col 22) and residue number
    (cols 23-26) of a PDB ATOM line; keep everything else unchanged."""
    return (line[:6] + "%5d" % atom_serial + line[11:21] + chain_id
            + "%4d" % resi_no + line[26:])


def splice(files_chain_map, out_name, with_ter=True):
    """Concatenate several .atm files into one PDB with rewritten chain IDs.
    files_chain_map: ordered list of (atm_filename, new_chain_id)"""
    out_lines = []
    atom_serial = 0
    for atm_name, chain_id in files_chain_map:
        src = os.path.join(HOMSTRAD_RHODANESE, atm_name)
        resi_no = 0
        prev_resi = None
        with open(src) as f:
            for line in f:
                if not line.startswith("ATOM"):
                    continue
                if len(line) < 54:
                    continue
                # count residues by residue-number change
                cur_resi = line[22:26]
                if cur_resi != prev_resi:
                    resi_no += 1
                    prev_resi = cur_resi
                atom_serial += 1
                out_lines.append(rewrite_atom(line, atom_serial, chain_id, resi_no))
        if with_ter:
            out_lines.append("TER\n")
    with open(os.path.join(SCRIPT_DIR, out_name), "w") as f:
        f.writelines(out_lines)
    print("generated %s: %d atoms, %d chains" %
          (out_name, atom_serial, len(files_chain_map)))


def write_chainmap(filename, pairs):
    """pairs: list of (chain1, chain2) tab-separated lines."""
    with open(os.path.join(SCRIPT_DIR, filename), "w") as f:
        for c1, c2 in pairs:
            f.write("%s\t%s\n" % (c1, c2))
    print("generated %s: %s" % (filename, pairs))


def write_short_pdb(filename):
    """2-residue chain (2 CA atoms) - too short (<3 residues) test."""
    lines = [
        "ATOM      1  N   ALA A   1      -1.000   0.000   0.000  1.00 20.00\n",
        "ATOM      2  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00\n",
        "ATOM      3  C   ALA A   1       1.000   0.000   0.000  1.00 20.00\n",
        "ATOM      4  N   ALA A   2       1.500   0.500   0.000  1.00 20.00\n",
        "ATOM      5  CA  ALA A   2       2.500   0.500   0.000  1.00 20.00\n",
        "ATOM      6  C   ALA A   2       3.500   0.500   0.000  1.00 20.00\n",
        "TER\n",
    ]
    with open(os.path.join(SCRIPT_DIR, filename), "w") as f:
        f.writelines(lines)
    print("generated %s: 2 residues" % filename)


def main():
    if not os.path.isdir(HOMSTRAD_RHODANESE):
        raise SystemExit("ERROR: HOMSTRAD Rhodanese dir not found: "
                         + HOMSTRAD_RHODANESE)

    # ---- Rhodanese 3+3 complex pair (main test data) ----
    splice([("1c25.atm", "A"), ("1e0ca1.atm", "B"), ("1e0ca2.atm", "C")],
           "complexA.pdb")
    splice([("1qb0a.atm", "A"), ("1rhs1.atm", "B"), ("1rhs2.atm", "C")],
           "complexB.pdb")

    # ---- chain-number mismatch variant (3 vs 2) ----
    splice([("1qb0a.atm", "A"), ("1rhs1.atm", "B")], "complexB_2chain.pdb")

    # ---- 2-residue short chain ----
    write_short_pdb("short.pdb")

    # ---- copy 4iaj/4jhm locally (F4 lock-conflict case uses bare filenames) ----
    for src_name in ("4iaj.pdb1", "4jhm.pdb1"):
        src = os.path.join(CLANGUAGE2CPLUS_DATA, src_name)
        dst = os.path.join(SCRIPT_DIR, src_name)
        if not os.path.isfile(src):
            raise SystemExit("ERROR: source data not found: " + src)
        if not os.path.isfile(dst) or os.path.getmtime(src) != os.path.getmtime(dst):
            shutil.copy2(src, dst)
        print("copied %s -> %s" % (src, dst))

    # ---- chainmap files ----
    write_chainmap("map_full.txt", [("A", "A"), ("B", "B"), ("C", "C")])
    write_chainmap("map_A.txt", [("A", "A")])
    write_chainmap("map_AB.txt", [("A", "A"), ("B", "B")])
    write_chainmap("map_swap.txt", [("A", "B"), ("B", "A")])
    write_chainmap("map_dup.txt", [("A", "A"), ("C", "A")])
    write_chainmap("map_dup1.txt", [("A", "A"), ("A", "B")])
    write_chainmap("map_nonexist.txt", [("X", "A")])

    # ---- type-mismatch mapping (RNA chain A -> protein chain A) ----
    write_chainmap("map_rna_type.txt", [("A", "A")])
    # ---- 4iaj vs 4jhm crossed mapping (4iaj chain A -> 4jhm chain B) ----
    write_chainmap("map_4iaj_AtoB.txt", [("A", "B")])

    print("ALL DATA GENERATED in %s" % SCRIPT_DIR)


if __name__ == "__main__":
    main()
