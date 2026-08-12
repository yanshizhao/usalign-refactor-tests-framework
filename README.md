# usalign-refactor-tests-framework

USalign 的整体测试框架，用于验证对 [USalign](https://zhanggroup.org/US-align/) 源码的修改不引入功能回归或性能退化。本框架按需求模块化组织——当有新的测试需求时，只需在 `scripts/` 下新增对应的子测试流程即可。

> **目录布局要求**：本仓库必须与 `USalign/` 源码目录放在同一父目录下。

## 目录结构

```
usalign-refactor-tests-framework/
└── scripts/
    ├── cLanguage2Cplus/   ← USalign 通用回归与性能测试
    ├── mm1/               ← 寡聚体（-mm 1）批量目录模式测试
    ├── upgmatree/         ← 多结构比对（-mm 4 / MSTA）测试
    └── chainmap_local/    ← -chainmap 局部约束（-mm 1 链映射硬约束）测试
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

### upgmatree

验证 USalign `-mm 4`（MSTA: Multiple Structure Alignment）多结构比对流程。使用 HOMSTRAD 数据库 ABC_tran（ABC transporter）家族的 6 条蛋白质链，测试 UPGMA 树构建、多结构比对及输出文件生成。

- **测试类型**：功能验证
- **详细文档**：[scripts/upgmatree/README.md](scripts/upgmatree/README.md) | [English](scripts/upgmatree/README_EN.md)

### chainmap_local

验证 USalign `-chainmap` 局部约束功能（仅 `-mm 1` 复合物比对）：用户指定的链映射对作为硬约束锁定（含交叉映射），剩余链按 TM-score 自动择优。包含回归测试（R1/R2/R3，与 master 基线 diff，差异属预期清单）与 23 个功能断言用例（F1-F6 / E1-E5 / D1-D2 / B1-B4 / G6-G11），覆盖映射锁定、自动择优、输入防御（重复键/重复目标/类型不匹配/链不存在）、低分场景映射链保留（回退/迭代/剔除豁免）、链数不匹配与混合分子等边界组合、配对汇总输出格式。测试数据含 Rhodanese 3+3 拼接复合物（带标准答案 TM4）、4iaj/4jhm 真实低分复合物与临界区合成数据。

- **测试类型**：功能回归 + 功能断言
- **用例清单**：[功能用例](scripts/chainmap_local/testcases_feature.txt) | [回归用例](scripts/chainmap_local/testcases_regression.txt)
- **脚本**：`create_baseline.py`（master 基线）/ `run_regression.py`（R1-R3 回归）/ `run_feature_test.py`（23 个功能用例断言）

---

后续如有新的测试需求（如特定算法模块验证、跨平台兼容性测试等），参照现有子流程的模式在 `scripts/` 下新增即可。

## 核心原理

所有子测试流程都采用**双可执行文件比对模式**：

```
USalign 源码
  ├── master 分支编译 → 原始版 → baseline/（黄金标准）
  └── 目标分支编译   → 修改版 → current/ → 逐字节/逐行比对
```

其中 chainmap_local 在回归比对之外，另以关键行断言方式验证局部约束新行为（映射锁定、防御警告、未配对归因等，见 `testcases_feature.txt`）。详细说明见各子测试流程的 README。
