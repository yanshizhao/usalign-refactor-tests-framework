# usalign-refactor-tests-framework

A modular test framework for verifying that modifications to the [USalign](https://zhanggroup.org/US-align/) source code do not introduce functional regressions or performance degradation. The framework is organized by requirement modules — when a new testing need arises, simply add a corresponding sub-test workflow under `scripts/`.

> **Directory layout requirement**: This repository must be placed in the same parent directory as the `USalign/` source directory.

## Directory Structure

```
usalign-refactor-tests-framework/
└── scripts/
    ├── cLanguage2Cplus/   ← USalign general regression & performance tests
    ├── mm1/               ← Oligomer (-mm 1) batch directory mode tests
    ├── upgmatree/         ← Multiple structure alignment (-mm 4 / MSTA) tests
    └── chainmap_local/    ← -chainmap local-constraint (-mm 1 chain mapping hard lock) tests
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

### chainmap_local

Validates the USalign `-chainmap` local-constraint feature (oligomer alignment `-mm 1` only): user-specified chain mapping pairs are locked as hard constraints (including crossed mappings), while the remaining chains are auto-matched by TM-score. Contains regression tests (R1/R2/R3, diffed against the master baseline; differences belong to the expected-difference list) and 23 functional assertion cases (F1-F6 / E1-E5 / D1-D2 / B1-B4 / G6-G11), covering mapping locks, auto-matching, input defenses (duplicate key / duplicate target / type mismatch / nonexistent chain), low-score mapped-chain retention (fallback / iteration / dimer exclusion exemption), boundary combinations (chain-count mismatch, mixed molecules), and pairing-summary output formats. Test data includes the spliced Rhodanese 3+3 complexes (with known-answer TM4 values), the real low-score 4iaj/4jhm complex pair, and synthetic critical-zone data.

- **Test type**: Functional regression + functional assertion
- **Case lists**: [Functional cases](scripts/chainmap_local/testcases_feature.txt) | [Regression cases](scripts/chainmap_local/testcases_regression.txt)
- **Scripts**: `create_baseline.py` (master baseline) / `run_regression.py` (R1-R3 regression) / `run_feature_test.py` (23 functional assertion cases)

---

For future testing needs (e.g., specific algorithm module verification, cross-platform compatibility testing, etc.), follow the pattern of existing sub-workflows and add new ones under `scripts/`.

## Core Principle

All sub-test workflows use a **dual-executable comparison model**:

```
USalign source code
  ├── master branch compile → original version → baseline/ (gold standard)
  └── target branch compile → modified version → current/ → byte-by-byte / line-by-line comparison
```

In addition to the regression comparison, chainmap_local asserts new local-constraint behaviors via key-line checks (mapping locks, defense warnings, unpaired-reason attribution, etc.; see `testcases_feature.txt`). See each sub-test workflow's README for detailed instructions.
