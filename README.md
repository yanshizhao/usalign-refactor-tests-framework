# usalign-refactor-tests-framework

USalign 的整体测试框架，用于验证对 [USalign](https://zhanggroup.org/US-align/) 源码的修改不引入功能回归或性能退化。本框架按需求模块化组织——当有新的测试需求时，只需在 `scripts/` 下新增对应的子测试流程即可。

> **目录布局要求**：本仓库必须与 `USalign/` 源码目录放在同一父目录下。

## 目录结构

```
usalign-refactor-tests-framework/
└── scripts/
    ├── cLanguage2Cplus/   ← USalign 通用回归与性能测试
    └── mm1/               ← 寡聚体（-mm 1）批量目录模式测试
```

## 子测试流程

### cLanguage2Cplus

验证 USalign **全部功能**的回归和性能，覆盖 14 个功能用例、4 个性能用例以及 4 个独立程序（TMscore、HwRMSD、MMalign、pdb2ss）的子测试。

- **测试类型**：功能回归 + 性能回归
- **详细文档**：[scripts/cLanguage2Cplus/README.md](scripts/cLanguage2Cplus/README.md)

### mm1

验证 USalign `-mm 1`（寡聚体比对）与批量目录模式（`-dir`、`-dir1`、`-dir2`）的组合功能，包含三层测试体系：回归测试、Guard 参数约束测试、Batch 交叉验证测试。

- **测试类型**：功能回归 + Guard + Batch 交叉验证
- **详细文档**：[scripts/mm1/README.md](scripts/mm1/README.md)

---

后续如有新的测试需求（如特定算法模块验证、跨平台兼容性测试等），参照现有子流程的模式在 `scripts/` 下新增即可。

## 核心原理

所有子测试流程都采用**双可执行文件比对模式**：

```
USalign 源码
  ├── master 分支编译 → 原始版 → baseline/（黄金标准）
  └── 目标分支编译   → 修改版 → current/ → 逐字节/逐行比对
```

详细说明见各子测试流程的 README。
