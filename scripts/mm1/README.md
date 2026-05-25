# mm1 - USalign 寡聚体批量比对测试框架

**mm1** 是 USalign `-mm 1`（寡聚体/多链复合物比对，MMalign）与目录批量模式（`-dir`、`-dir1`、`-dir2`）的回归测试套件。

> **重要**: `usalign-refactor-tests-framework` 要和源码文件 `USalign` 放在同一级目录下。

## 总体层级关系

```
D:\qlab\USalign-master\
├── USalign\                              ← 源码仓库（USalign.cpp 在此）
└── usalign-refactor-tests-framework\     ← 测试框架仓库（本仓库）
    └── scripts\
        ├── cLanguage2Cplus\              ← USalign 通用回归 & 性能测试
        └── mm1\                          ← 寡聚体批量比对测试（本目录）
```

## 目录结构

```
mm1/
├── data/
│   ├── US735192405.pdb                   # -dir1/-dir2 模式的固定目标结构
│   └── MSTATest/
│       ├── list.txt                      # 批量模式的 PDB 列表（3 个结构）
│       ├── US7351924051.pdb              # RNA 多结构比对测试数据
│       ├── US7351924052.pdb
│       └── US7351924053.pdb
│
├── dir1baseline/                         # -dir1 单对基线（master 分支生成）
├── dir2baseline/                         # -dir2 单对基线（master 分支生成）
├── dirbaseline/                          # -dir  单对基线（master 分支生成）
│
├── dir1result/                           # -dir1 测试运行输出（gitignore）
├── dir2result/                           # -dir2 测试运行输出（gitignore）
├── dirresult/                            # -dir  测试运行输出（gitignore）
├── dir1diff/                             # -dir1 diff 输出（gitignore）
├── dir2diff/                             # -dir2 diff 输出（gitignore）
├── dirdiff/                              # -dir  diff 输出（gitignore）
│
├── dir1_mm1_generate_baseline.py         # -dir1 基线生成脚本
├── dir1_mm1_test.py                      # -dir1 测试运行器
├── dir1_mm1_test_cases.txt               # -dir1 回归测试用例
├── dir1_mm1_feature_cases.txt            # -dir1 Guard + Batch 用例
│
├── dir2_mm1_generate_baseline.py         # -dir2 基线生成脚本
├── dir2_mm1_test.py                      # -dir2 测试运行器
├── dir2_mm1_test_cases.txt               # -dir2 回归测试用例
├── dir2_mm1_feature_cases.txt            # -dir2 Guard + Batch 用例
│
├── dir_mm1_generate_baseline.py          # -dir  基线生成脚本
├── dir_mm1_test.py                       # -dir  测试运行器
├── dir_mm1_test_cases.txt                # -dir  回归测试用例
├── dir_mm1_feature_cases.txt             # -dir  Guard + Batch 用例
│
├── CLAUDE.md                             # Claude Code 指导文件
├── IMPLEMENTATION_PLAN.txt               # 详细实现方案
├── WORK_LOG.txt                          # 工作日志
├── .gitignore                            # 忽略 result/diff 目录
└── README.md                             # 本文件
```

## 背景

### 什么是 mm1？

**mm1** = USalign 的 `-mm 1` 模式，即 **寡聚体/多链复合物结构比对**（MMalign 算法）。原始 USalign 代码中 `-dir` 与 `-mm 1` 被硬编码互斥，且 `-dir1` / `-dir2` 在 `-mm 1` 模式下会产生错误结果（将所有文件合并为一个巨型复合物）。

### USalign-beta 分支新增功能

`USalign-beta` 分支对 `USalign.cpp` 进行了 3 个递进式功能提交，使寡聚体比对支持批量目录模式：

| 提交 | 功能 | 说明 |
|------|------|------|
| `3e5d73d` | Phase 1: `-dir1` + `-mm 1` | 目录中每个复合物 vs 固定目标 |
| `ef648bf` | Phase 2: `-dir2` + `-mm 1` | 固定查询 vs 目录中每个复合物 |
| `42cc64f` | Phase 3: `-dir` + `-mm 1` | 目录内寡聚体全对全比对（上三角） |

参见 `IMPLEMENTATION_PLAN.txt` 获取完整技术方案。

## 快速开始

### 前置条件

- Python 3.x
- g++（用于编译 USalign）
- Git（源码仓库 `USalign` 需要是 Git 仓库，有 `master` 和 `USalign-beta` 分支）
- 确保 `usalign-refactor-tests-framework` 和 `USalign` 在同一父目录下

### 运行测试

所有命令在 `mm1/` 目录下执行：

```bash
cd D:\qlab\USalign-master\usalign-refactor-tests-framework\scripts\mm1
```

#### 1. 生成基线（仅需执行一次）

基线始终从 **master 分支**（未修改原始版本）编译生成：

```bash
# -dir1 基线
python dir1_mm1_generate_baseline.py

# -dir2 基线
python dir2_mm1_generate_baseline.py

# -dir  基线
python dir_mm1_generate_baseline.py
```

每个脚本自动：切换到 master → 编译 → 生成单对基线 → 恢复原分支。

#### 2. 运行回归测试

测试在 **USalign-beta 分支**（或通过 `--branch` 指定）上执行：

```bash
# -dir1 测试（回归 + Guard + Batch）
python dir1_mm1_test.py

# -dir2 测试（回归 + Guard + Batch）
python dir2_mm1_test.py

# -dir  测试（回归 + Guard + Batch）
python dir_mm1_test.py

# 指定其他目标分支
python dir_mm1_test.py --branch my-feature-branch
```

查看帮助：

```bash
python dir_mm1_test.py --help
python dir1_mm1_test.py --help
python dir2_mm1_test.py --help
```

## 测试用例格式

### 回归测试用例 (`*_test_cases.txt`)

每行定义一个单对测试用例，Tab 分隔：

```
<用例名>	<工作目录>	<命令行参数...>
```

工作目录相对于项目根目录（即 `USalign/` 和 `usalign-refactor-tests-framework/` 的父目录）。例如：

```
US7351924051_vs_US7351924052	usalign-refactor-tests-framework/scripts/mm1/data/MSTATest	US7351924051.pdb US7351924052.pdb -mm 1 -ter 0
```

- `#` 开头的行为注释
- 用例名用于生成基线/结果/diff 文件的命名

### Feature 测试用例 (`*_feature_cases.txt`)

包含两类测试：

**GUARD 测试**：验证参数约束，期望程序以非零退出码退出并输出特定子串：

```
GUARD_<名称>	<工作目录>	<命令行参数>	# EXPECT:<期望的错误子串>
```

**BATCH 测试**：验证批量模式输出。将批量输出按结构对拆分，与单对基线做交叉验证：

```
BATCH_<名称>	<工作目录>	<命令行参数>
```

## 测试架构

### 双分支策略

测试框架通过比对两个版本的输出来检测回归：

| 版本 | 编译来源 | 用途 |
|------|----------|------|
| 基线 | `master` 分支 | 生成"黄金标准"预期输出 |
| 当前 | `USalign-beta`（或指定分支） | 被测试的修改版本 |

脚本自动处理分支切换、编译、测试、恢复全过程。

### 三层测试体系

每个 `-dir` / `-dir1` / `-dir2` 模式都包含三层测试：

```
┌─────────────────────────────────────────────┐
│  1. 回归测试 (Regression)                    │
│     单对运行 → 逐行 diff vs master 基线       │
│     - outfmt 2 (表格格式)                    │
│     - outfmt -1 (详细格式 + 旋转矩阵)          │
├─────────────────────────────────────────────┤
│  2. Guard 测试                               │
│     验证参数约束 & 互斥检查                    │
│     - 期望非零退出码                           │
│     - 期望特定错误子串                         │
├─────────────────────────────────────────────┤
│  3. Batch 测试 (Split & Cross-Validate)      │
│     拆分批量输出 → 重构单对 → diff vs 基线      │
│     - outfmt 2: 按表格行拆分                   │
│     - outfmt -1: 按 "Name of Structure_1:" 块拆分 │
└─────────────────────────────────────────────┘
```

### 智能对比策略

输出对比分为三类判定：

| 状态 | 含义 |
|------|------|
| **PASS** | 输出与基线完全一致 |
| **WARNING** | 仅有非业务内容差异（如 CPU 时间、空行） |
| **FAIL** | 业务内容差异（比对分数、序列等核心输出不一致） |

此策略避免了因环境性能波动导致的假阳性。

### Guard 测试覆盖的约束

| 约束 | 含义 |
|------|------|
| `-mm 2` + `-dir` | `-mm 2`（MMdock）仍然禁止与目录模式组合 |
| `-chainmap` + 目录模式 | 批量模式下每对可能需要不同链映射，禁止全局复用 |
| `-ter 2` + `-mm 1` | 寡聚体模式必须使用 `-ter 0` 或 `-ter 1` |
| `-o` + `-dir` | 目录模式下禁止输出叠加结构文件（会互相覆盖） |
| `-dir` + `-dir1` 互斥 | 不同类型的目录模式不能同时使用 |

### 输出规范化

所有输出在写入文件前进行路径规范化：
- Windows 反斜杠 → 正斜杠
- 剥离所有目录前缀（只保留文件名），确保基线在不同机器间可移植
- 不修改任何业务数据内容

## 数据说明

### 测试数据来源

| 文件 | 来源 | 用途 |
|------|------|------|
| `data/US735192405.pdb` | MSTA RNA 测试集 | -dir1/-dir2 的固定目标 |
| `data/MSTATest/US7351924051-3.pdb` | MSTA RNA 测试集 | 批量目录中的测试结构 |
| `data/MSTATest/list.txt` | 手工创建 | 批量模式的结构列表 |

所有测试结构均为 RNA 多结构比对测试集（MSTA Test）中的结构，包含多条链，适合验证寡聚体比对逻辑。

### 目录生成物

以下目录是脚本运行时自动生成的，**不纳入版本控制**（已在 `.gitignore` 中忽略）：

- `dir1result/`、`dir2result/`、`dirresult/` — 测试运行输出
- `dir1diff/`、`dir2diff/`、`dirdiff/` — diff 输出

## 与 cLanguage2Cplus 的关系

| 维度 | cLanguage2Cplus | mm1 |
|------|-----------------|-----|
| 测试范围 | USalign 全部功能 | 仅 `-mm 1` + 目录模式 |
| 测试类型 | 功能回归 + 性能回归 | 功能回归 + Guard + Batch 交叉验证 |
| 目标分支 | `master` vs 当前修改 | `master` vs `USalign-beta` |
| 可执行文件 | `USalign_orig.exe` / `USalign_mod.exe` | `USalign_dir_mm1.exe` 等 |
| 数据 | 蛋白质 + RNA，多种格式 | RNA 寡聚体（MSTA 测试集） |

## 可执行文件命名

每个模式使用独立的可执行文件，避免 Windows 下文件占用冲突：

| 模式 | 可执行文件 |
|------|-----------|
| `-dir1` | `USalign_dir1_mm1.exe` |
| `-dir2` | `USalign_dir2_mm1.exe` |
| `-dir` | `USalign_dir_mm1.exe` |

所有可执行文件编译自 `../USalign/USalign.cpp`（根据当前分支），位于 `USalign/` 目录下。

## 常见问题

### 基线目录不存在

```
[ERROR] Baseline directory not found: .../dirbaseline
```

**解决**: 先运行对应的 `generate_baseline.py` 生成基线。

### 编译失败

```
[ERROR] Compilation failed
```

**原因**: 通常是 g++ 未安装或不在 PATH 中。确认 `g++ --version` 可用。

### 分支切换失败

确保 `../USalign/` 目录是 Git 仓库，且有 `master` 分支。`USalign-beta` 分支仅在运行测试时需要（基线生成只需要 master）。

### 单对基线 vs 批量基线

本框架采用 **Split Cross-Validation** 策略：基线只生成单对（single-pair）输出。批量测试时，将批量输出按结构对拆分，再与单对基线对比。这意味着：
- 不需要为批量模式单独生成基线
- 单对基线 = 批量交叉验证的"黄金标准"
