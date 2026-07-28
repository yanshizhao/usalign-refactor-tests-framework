# upgmatree — USalign `-mm 4` (MSTA) Test Data

## Description

This directory contains 6 protein chains from the **HOMSTRAD** **ABC_tran** (ABC transporter) family, used for testing **USalign**'s `-mm 4` (MSTA: Multiple Structure Alignment) workflow.

### Files

| File | Description |
|------|-------------|
| `1b0ua.atm` ~ `1g6ha.atm` | 6 single-chain PDB-format structure files |
| `list.txt` | Input list, one filename per line, for `-dir` mode |
| `ABC_tran.ali` | HOMSTRAD multiple sequence alignment |
| `ABC_tran.malf` | HOMSTRAD structure superposition transform |
| `ABC_tran-sup.pdb` | HOMSTRAD reference superposition |
| `README_EN.md` | This file |

## Compilation

### Using Makefile

```bash
# Run from the USalign source directory
cd ../../../USalign

# Linux / macOS
make clean
make

# Windows (MSYS2/MinGW)
mingw32-make clean
mingw32-make
```

The Makefile automatically applies the appropriate flags per platform (`-static` on Windows, none on Linux/macOS).

### Manual Compilation

```bash
cd ../../../USalign

# Linux
g++ -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp

# Windows (MSYS2/MinGW)
g++ -static -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp

# macOS（-static not supported）
g++ -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp
```

> **Notes:**
> - Omit `-fopenmp` to disable OpenMP parallelization.
> - On Windows, the resulting `USalign.exe` is statically linked and does not depend on MSYS2 DLLs; it can run on any Windows machine without additional runtime dependencies.

## Usage

All commands below assume the current working directory is the USalign source directory (`../../../USalign`).

### Basic Command

```bash
# Run from USalign directory
./USalign -dir ../usalign-refactor-tests-framework/scripts/upgmatree/ \
          ../usalign-refactor-tests-framework/scripts/upgmatree/list.txt \
          -mm 4
```

### Windows PowerShell

```powershell
.\USalign.exe -dir ..\usalign-refactor-tests-framework\scripts\upgmatree\ `
              ..\usalign-refactor-tests-framework\scripts\upgmatree\list.txt `
              -mm 4
```

## Output

The following files are generated in the **current working directory** (i.e., the USalign directory):

| File | Description |
|------|-------------|
| `upgma_tree.txt` | UPGMA phylogenetic tree (Newick format) |
| `upgma_tree.svg` | UPGMA tree visualization (SVG) |
| `upgma_tree.dist` | Pairwise TM-score distance matrix |

Terminal output includes: UPGMA tree, multiple structure alignment (FASTA-like format), and summary statistics (average aligned length, RMSD, TM-score, sequence identity).