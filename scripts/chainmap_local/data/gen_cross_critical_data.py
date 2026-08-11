# -*- coding: utf-8 -*-
"""Generate critical-zone data for cross-chain adoption regression (R3/G11).

Background: MMalign_dimer's cross_score double-count bug (fixed 2026-08-11)
inflated cross_score ~2x, widening the adoption condition from
`cross > iteration` to `cross > iteration/2`. Data whose real cross score
falls in [iteration/2, iteration] then adopts a WORSE cross-chain result.

This dataset (d=08) sits exactly in that zone:
  - both complexes: chain A = phase-0 sine curve (perfect match)
  - chain B: same shape, but its y-offset differs by 8 A between complexes
    (50 vs 58) -> joint-rotation compromise lowers cross below iteration,
    while keeping it above iteration/2 -> buggy adopts, fixed rejects.

Expected (fixed) pairing: B->B (A chains paired), chain A of structure 2
removed by quality protection. Buggy pairing: A->A (B chains removed).
"""
import math

LEN = 10          # residues per chain (>= 3, Kabsch lower bound)
OFFSET_B1 = 50.0  # structure-1 chain B y-offset
OFFSET_B2 = 58.0  # structure-2 chain B y-offset (d = 8.0)


def chain_atoms(chain_id, x0, phase, offset_y, len_res=LEN, res_start=1):
    lines = []
    for r in range(len_res):
        x = x0 + r
        y = math.sin(0.7 * r + phase) + offset_y
        z = math.cos(0.5 * r + phase)
        lines.append(
            "ATOM  %5d  CA  ALA %s%4d    %8.3f%8.3f%8.3f  1.00  0.00           C"
            % (res_start + r, chain_id, r + 1, x, y, z))
    return lines


def write_pdb(filename, chains):
    body = []
    for atoms in chains:
        body.extend(atoms)
        body.append("TER")
    body.append("END")
    with open(filename, "w") as f:
        f.write("\n".join(body) + "\n")


def main():
    # structure 1: A = phase 0 at origin; B = phase 1.7, y-offset 50
    a1 = chain_atoms("A", 0.0, 0.0, 0.0)
    b1 = chain_atoms("B", 0.0, 1.7, OFFSET_B1)
    # structure 2: A identical to structure-1 A; B shifted by d=8
    a2 = chain_atoms("A", 0.0, 0.0, 0.0)
    b2 = chain_atoms("B", 0.0, 1.7, OFFSET_B2)
    write_pdb("crit_A.pdb", [a1, b1])
    write_pdb("crit_B.pdb", [a2, b2])
    print("crit_A.pdb / crit_B.pdb generated (LEN=%d, d=%.1f)" % (LEN, OFFSET_B2 - OFFSET_B1))


if __name__ == "__main__":
    main()
