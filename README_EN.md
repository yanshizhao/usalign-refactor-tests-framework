# usalign-refactor-tests-framework

A modular test framework for verifying that modifications to the [USalign](https://zhanggroup.org/US-align/) source code do not introduce functional regressions or performance degradation. The framework is organized by requirement modules — when a new testing need arises, simply add a corresponding sub-test workflow under `scripts/`.

> **Directory layout requirement**: This repository must be placed in the same parent directory as the `USalign/` source directory.

## Directory Structure

```
usalign-refactor-tests-framework/
└── scripts/
    ├── cLanguage2Cplus/   ← USalign general regression & performance tests
    ├── mm1/               ← Oligomer (-mm 1) batch directory mode tests
    └── upgmatree/         ← Multiple structure alignment (-mm 4 / MSTA) tests
```

## Sub-Test Workflows

### cLanguage2Cplus

Validates regression and performance of **all USalign functionality**, covering 14 functional test cases, 4 performance test cases, and sub-tests for 4 standalone programs (TMscore, HwRMSD, MMalign, pdb2ss).

- **Test type**: Functional regression + performance regression
- **Detailed documentation**: [scripts/cLanguage2Cplus/README.md](scripts/cLanguage2Cplus/README.md)

### mm1

Validates the combined functionality of USalign `-mm 1` (oligomer alignment) with batch directory modes (`-dir`, `-dir1`, `-dir2`), featuring a three-layer test system: regression tests, guard parameter constraint tests, and batch cross-validation tests.

- **Test type**: Functional regression + Guard + Batch cross-validation
- **Detailed documentation**: [scripts/mm1/README.md](scripts/mm1/README.md)

### upgmatree

Validates the USalign `-mm 4` (MSTA: Multiple Structure Alignment) workflow. Uses 6 protein chains from the HOMSTRAD ABC_tran (ABC transporter) family to test UPGMA tree construction, multiple structure alignment, and output file generation.

- **Test type**: Functional validation
- **Detailed documentation**: [scripts/upgmatree/README_EN.md](scripts/upgmatree/README_EN.md) | [中文](scripts/upgmatree/README.md)

---

For future testing needs (e.g., specific algorithm module verification, cross-platform compatibility testing, etc.), follow the pattern of existing sub-workflows and add new ones under `scripts/`.

## Core Principle

All sub-test workflows use a **dual-executable comparison model**:

```
USalign source code
  ├── master branch compile → original version → baseline/ (gold standard)
  └── target branch compile → modified version → current/ → byte-by-byte / line-by-line comparison
```

See each sub-test workflow's README for detailed instructions.
