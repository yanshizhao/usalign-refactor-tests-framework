# cLanguage2Cplus — USalign C→C++ 重构 回归与性能测试框架

## 1. 概述

本目录是 **USalign** 的回归与性能测试框架。USalign 是一款通用的蛋白质/核酸结构比对工具，采用纯头文件 C++ 代码库设计，主入口为 `../../../USalign/USalign.cpp`（约 3600 行）。

> **目录布局要求**：`usalign-refactor-tests-framework/` 必须与 `USalign/` 源码目录放在同一级目录下，所有脚本中的相对路径（`../../../USalign/`）依赖此布局。

本框架的核心目的是验证对 USalign 源码的 C→C++ 风格重构**不引入功能回归和性能退化**。重构涉及 22 类 C 风格 → C++ 风格映射，覆盖全部 27 个源文件（15 `.h` + 12 `.cpp`），共计 51 个 commits。

## 2. 目录层级结构

### 2.1 总体层级

```
<workspace>/                        # 工作区根目录
├── USalign/                        # 源码仓库 (USalign-beta, 30 个源文件)
└── usalign-refactor-tests-framework/  # 测试框架仓库 (main)
    └── scripts/
        ├── cLanguage2Cplus/        # ★ 本目录 — 主回归测试框架
        └── mm1/                    # MMalign 独立功能测试
```

### 2.2 本目录详细层级

```
cLanguage2Cplus/                        # ★ 主回归测试框架
│
├── README.md                           # 本文件
├── CLAUDE.md                           # Claude Code 工作指导
│
├── 测试脚本 (Python)
│   ├── create_baseline.py              # 编译 master 原始版 → 生成功能基线 baseline/
│   ├── run_regression.py               # 编译 USalign-beta 修改版 → 逐字节比对 14 个功能用例
│   ├── create_perf_baseline.py         # 编译 master 原始版 → 生成性能基线 perf_baseline/
│   ├── run_perf_test.py                # 编译 USalign-beta 修改版 → 性能测试 (5次取平均)
│   ├── build_Small_DB.py               # 从 PDB 库随机抽取 100 个结构构建 smallDB
│   └── find_pdb_length.py              # 辅助工具 — 统计 PDB 文件残基数
│
├── 测试用例定义 (纯文本, 每行一个用例)
│   ├── testcases_functional.txt        # 14 个功能回归用例 (格式: <name> <workdir> <args...>)
│   └── testcases_performance.txt       # 4 个性能回归用例
│
├── baseline/                           # 原始版基线 — 14 个 .out + sup.pdb (create_baseline.py 生成)
├── current/                            # 修改版当前输出 (run_regression.py 运行时重建，每次清空)
├── diffs/                              # unified diff 文件 (run_regression.py 运行时重建)
├── perf_baseline/                      # 性能基线 — baseline.csv (create_perf_baseline.py 生成)
├── perf_current/                       # 当前性能 — performance.csv (run_perf_test.py 生成)
│
├── data/                               # ★ 测试数据
│   ├── 101m.pdb                         # 肌红蛋白 (单体)
│   ├── 1mba.pdb                         # 肌红蛋白 B 链 (单体)
│   ├── 1ajk.pdb                         # 单体结构
│   ├── 2ayh.pdb                         # 单体结构
│   ├── 1eh1.pdb                         # RNA 结构
│   ├── 1evv.pdb                         # RNA 结构
│   ├── 3am1.pdb                         # 单体结构
│   ├── 4iaj.pdb1                       # 多链结构 (二聚体)
│   ├── 4jhm.pdb1                       # 多链结构 (二聚体)
│   ├── 6b3rA.pdb / 6bq1A.pdb           # 性能测试用
│   ├── 6jxm.pdb                        # 单体结构
│   ├── 7o7lA.pdb / 7o7mA.pdb           # 性能测试用
│   ├── help/                            # TM-score 引导测试数据
│   │   ├── model.pdb / native.pdb       #   双结构 TM-score 评估
│   │   ├── modelComplex.pdb / nativeComplex.pdb  # 复合物 TM-score 评估
│   │   ├── align.txt                   #   序列比对引导文件 (HwRMSD)
│   │   ├── PDB1.sup.pdb / complex1.sup.pdb  # 叠合结构模板
│   ├── MSTATest/                        # RNA 多结构比对测试集
│   │   ├── US735192405.pdb ~ US73519240510.pdb  # 12 个 RNA 结构
│   │   └── list.txt                    #   文件列表
│   └── smallDB/                         # 数据库搜索子集 (100 个随机 PDB + list.txt)
│
├── standalone/                          # ★ 4 个独立程序子测试框架
│   ├── tmscore/                         # TMscore: 6 用例 (help目录下的全部示例)
│   │   ├── testcases.txt               #   用例定义
│   │   ├── create_baseline.py          #   从 master 提取 TMscore.cpp → 编译 → 生成基线
│   │   └── run_test.py                 #   编译 USalign-beta 源码 → 逐字节比对
│   ├── hwrmsd/                          # HwRMSD: 5 用例
│   │   ├── testcases.txt
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   ├── mmalign/                         # MMalign: 4 用例
│   │   ├── testcases.txt
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   └── pdb2ss/                          # pdb2ss: 2 用例
│       ├── testcases.txt
│       ├── create_baseline.py
│       └── run_test.py
│
├── docs/superpowers/specs/              # ★ 项目设计文档 (4 份)
│   ├── 2026-05-12-usalign-cpp-refactor-design.md         # 重构总体方案
│   ├── 2026-05-14-refactor-progress-log.md               # 重构详细进度日志
│   ├── 2026-05-21-refactor-final-summary.md              # 最终总结
│   └── 2026-05-21-usalign-l2h-pointer-to-container-design.md  # 二级指针→容器方案
│
├── USalign_orig.exe                    # 原始版可执行文件 (预编译, master 分支)
└── __pycache__/                        # Python 缓存
```

## 3. 快速开始

**前置条件**：
- GCC (`g++`) 可编译 USalign：需要 `-O3 -ffast-math`
- Python 3.6+
- 本目录下的 `.py` 脚本**必须在本目录内运行**

### 3.1 建立基线（修改源码前，仅执行一次）

```bash
cd cLanguage2Cplus

# 1. 生成功能基线 — 从 master 编译 USalign，执行 14 个用例，保存输出到 baseline/
python create_baseline.py

# 2. 生成性能基线 — 从 master 编译 USalign，4 个用例各跑 5 次，保存到 perf_baseline/baseline.csv
python create_perf_baseline.py
```

### 3.2 开发迭代（修改源码后，反复执行）

```bash
cd cLanguage2Cplus

# 1. 运行功能回归 — 从 USalign-beta 编译，逐字节比对 14 个用例
python run_regression.py

# 2. 运行性能回归 — 从 USalign-beta 编译，5 次取平均，对比基线
python run_perf_test.py
```

### 3.3 构建测试数据库（可选）

```bash
# 需要有 I-TASSER PDB 模板库，修改 build_Small_DB.py 中的 SOURCE_DIR 后运行
python build_Small_DB.py
```

## 4. 脚本详解

### 4.1 `create_baseline.py` — 功能基线生成

| 项目 | 说明 |
|------|------|
| **用途** | 生成回归测试的黄金标准输出 |
| **编译源** | `master` 分支的 `../../../USalign/USalign.cpp` |
| **产物** | `USalign_orig.exe` + `baseline/` 目录 (14 个 `.out` + `sup.pdb`) |
| **输入** | `testcases_functional.txt` |
| **执行时机** | 修改源码前**仅执行一次** |
| **工作原理** | 自动 checkout → `master`，编译原始版，逐条执行 14 个用例，捕获 stdout+stderr，经 `clean_slash()` 清洗后保存到 `baseline/` |

### 4.2 `run_regression.py` — 功能回归测试

| 项目 | 说明 |
|------|------|
| **用途** | 验证修改版输出与基线逐字节一致 |
| **编译源** | `USalign-beta` 分支的 `../../../USalign/USalign.cpp` |
| **产物** | `USalign_mod_<pid>.exe`+ `current/` (14 个 `_mod.out`) + `diffs/` (差异文件) |
| **输入** | `testcases_functional.txt` + `baseline/` |
| **执行时机** | 每次修改源码后 |
| **输出判定** | `PASS` = 逐字节一致 / `CHECK` = 有差异 (生成 `.diff`) / `ERROR` = 基线文件缺失 |
| **特殊处理** | `superposed_structure` 额外比对 `sup.pdb` 结构文件；自动清理 `.pml` 文件；`clean_slash()` 清洗 `Name of Structure_X:` 行的 `/` 前缀 |
| **注意** | 每次运行前自动清空 `current/` 和 `diffs/` 目录 |

### 4.3 `create_perf_baseline.py` — 性能基线生成

| 项目 | 说明 |
|------|------|
| **用途** | 生成性能参考基线 |
| **编译源** | `master` 分支 |
| **产物** | `USalign_orig.exe` + `perf_baseline/baseline.csv` |
| **输入** | `testcases_performance.txt` |
| **参数** | 每个用例运行 **5 次**，取 `#Total CPU time` 平均值 |
| **执行时机** | 修改源码前仅执行一次 |

### 4.4 `run_perf_test.py` — 性能回归测试

| 项目 | 说明 |
|------|------|
| **用途** | 检测修改是否引入性能退化 |
| **编译源** | `USalign-beta` 分支 |
| **产物** | `USalign_mod_<pid>.exe` + `perf_current/performance.csv` |
| **输入** | `testcases_performance.txt` + `perf_baseline/baseline.csv` |
| **参数** | 每个用例运行 **5 次**，取平均值 |
| **判定阈值** | `<20%` → PASS / `20%-50%` → WARNING / `>50%` → FAIL |
| **计算方式** | `pct = (T_current - T_baseline) / T_baseline * 100` |

### 4.5 `build_Small_DB.py` — 数据库构建脚本

| 项目 | 说明 |
|------|------|
| **用途** | 从 I-TASSER PDB 模板库随机抽取 100 个结构，构建 `data/smallDB/` |
| **输出** | `data/smallDB/` 目录 (100 个 `.pdb` + `list.txt`) |
| **配置** | 需修改脚本中 `SOURCE_DIR` 为实际 PDB 目录路径 |
| **固定种子** | `random.seed(42)`，确保可重复 |

### 4.6 独立程序测试脚本

每个独立程序 (`standalone/<程序名>/`) 下有两个核心脚本：

**`create_baseline.py`**：从 `master` 分支提取独立程序的 `.cpp` 源码 → 编译 → 执行用例 → 保存基线输出到 `baseline/`

**`run_test.py`**：切换到 `USalign-beta` → 编译独立程序 → 执行用例 → 逐字节比对基线。比对前通过 `strip_cpu_time()` 过滤 `#Total CPU time` 行（CPU 时间自然波动，不作为回归依据）。

## 5. 测试用例说明

### 5.1 用例格式

```
<用例名称> <工作目录> <USalign 命令行参数...>
```

- `<工作目录>` **相对于 `data/` 目录**，用 `.` 表示 data 根目录
- 以 `#` 开头的行是注释
- 脚本执行 USalign 前会将 `cwd` 设为 `data/<工作目录>`

### 5.2 功能测试用例 (14 个)

| # | 用例名 | 工作目录 | 参数 | 测试场景 |
|---|--------|---------|------|---------|
| 1 | `standard_protein` | `.` | `101m.pdb 1mba.pdb -outfmt -1 -m -` | 标准蛋白单体比对 + 旋转矩阵 |
| 2 | `multichain_split` | `.` | `4iaj.pdb1 4jhm.pdb1 -ter 1 -outfmt -1 -m -` | 多链拆分 (TER 记录分割) |
| 3 | `oligomer` | `.` | `4iaj.pdb1 4jhm.pdb1 -mm 1 -outfmt -1 -m -` | 寡聚体比对 (`-mm 1`) |
| 4 | `circular_permutation` | `.` | `1ajk.pdb 2ayh.pdb -mm 3 -outfmt -1 -m -` | 循环置换比对 (`-mm 3`) |
| 5 | `fully_non_seq` | `.` | `1eh1.pdb 1evv.pdb -mm 5 -atom PC4' -outfmt -1 -m -` | 完全非顺序 RNA 比对 (`-mm 5`) |
| 6 | `semi_non_seq` | `.` | `1ajk.pdb 2ayh.pdb -mm 6 -outfmt -1 -m -` | 半非顺序比对 (`-mm 6`) |
| 7 | `superposed_structure` | `.` | `101m.pdb 1mba.pdb -o sup` | 叠合结构输出 (生成 sup.pdb) |
| 8 | `tmscore_resid` | `help` | `model.pdb native.pdb -TMscore 1 -outfmt -1 -m -` | TM-score 残基引导 |
| 9 | `tmscore_seqalign` | `help` | `model.pdb native.pdb -TMscore 5 -outfmt -1 -m -` | TM-score 序列比对引导 |
| 10 | `complex_chainid` | `help` | `modelComplex.pdb nativeComplex.pdb -TMscore 2 -outfmt -1 -m -` | 复合物链 ID 引导 |
| 11 | `complex_chainmap` | `help` | `modelComplex.pdb nativeComplex.pdb -TMscore 6 -outfmt -1 -m -` | 复合物链映射引导 |
| 12 | `msta_rna` | `MSTATest` | `-dir .\ list.txt -suffix .pdb -mm 4 -mol RNA -outfmt -1 -m -` | RNA 多结构比对 (MSTA) |
| 13 | `all_vs_all` | `MSTATest` | `-dir .\ list.txt -suffix .pdb -outfmt -1 -m -` | 全对全比对 |
| 14 | `database_search` | `.` | `1mba.pdb -dir2 smallDB smallDB\list.txt -suffix .pdb -fast -outfmt -1 -m -` | 数据库搜索 (快速模式) |

> **说明**：`-outfmt -1` 表示完整输出（不含版本信息），使输出具有确定性。`-m -` 将旋转矩阵输出到 stdout。

### 5.3 性能测试用例 (4 个)

| # | 用例名 | 参数 | 测试场景 |
|---|--------|------|---------|
| 1 | `perf_fast1` | `6bq1A.pdb 6b3rA.pdb -fast` | 快速蛋白比对 |
| 2 | `perf_fast2` | `7o7lA.pdb 7o7mA.pdb -fast` | 快速蛋白比对 |
| 3 | `perf_msta_rna` | `-dir .\ list.txt -suffix .pdb -mm 4 -mol RNA` | RNA 多结构比对 |
| 4 | `perf_database_search` | `-dir . list.txt -suffix .pdb -fast` | 数据库搜索 |

### 5.4 独立程序测试用例

| 程序 | 用例数 | 测试覆盖 |
|------|--------|---------|
| TMscore | 6 | 基本 TM-score、复合物、自定义 d0、指定长度、叠合输出、序列比对 |
| HwRMSD | 5 | 基本 RMSD、自定义长度、比对引导、序列引导、矩阵输出 |
| MMalign | 4 | 基本寡聚体比对、自定义 d0、比对引导、矩阵输出 |
| pdb2ss | 2 | help 目录 + 顶层 data 目录各 1 个 |

## 6. 工作原理

### 6.1 双可执行文件比对模式

```
┌──────────────┐       ┌──────────────┐
│ USalign_orig │       │ USalign_mod  │
│ (master 编译) │       │ (USalign-beta│
│              │       │  编译)        │
└──────┬───────┘       └──────┬───────┘
       │ 输出                  │ 输出
       ▼                       ▼
  baseline/               current/
  (黄金标准)               (修改版)
       │                       │
       └─────── 逐字节比对 ─────┘
                    │
            PASS / CHECK (diff)
```

两个可执行文件都从 `../../../USalign/USalign.cpp` 编译，区别在于使用的 Git 分支不同：
- **原始版** = `master` 分支编译（重构前的干净代码）
- **修改版** = `USalign-beta` 分支编译（包含全部 C→C++ 重构的代码）

### 6.2 输出比对逻辑

`run_regression.py` 进行**逐字节比对**：

1. 捕获 USalign 的 `stdout + stderr`，调用 `clean_slash()` 移除 `Name of Structure_X:` 行多余的 `/` 前缀（USalign 输出的已知瑕疵）
2. 使用 `bdata == cdata` 逐字节比较基线输出和当前输出
3. 不一致时在 `diffs/<用例名>.diff` 中生成 unified diff

### 6.3 关键约定

- baseline 输出文件命名为 `<用例名>.out`，修改版追加 `_mod` 后缀（如 `standard_protein_mod.out`）
- `superposed_structure` 额外比对生成的 `sup.pdb` 结构文件
- `current/`、`diffs/`、`perf_current/` 每次运行时自动清空重建，**切勿在其中存放重要文件**
- Windows 下 `-dir` / `-dir2` 使用反斜杠路径分隔符 (`.\`)
- 测试完成后自动恢复到运行前的 Git 分支

## 7. 依赖与编译

| 项目 | 说明 |
|------|------|
| 编译器 | `g++`，需要 `-O3 -ffast-math -lm`（Windows 可能需要 `-static`） |
| Python | 3.6+，仅使用标准库 (`subprocess`, `difflib`, `csv`, `pathlib`, `shutil`, `re`) |
| USalign 源码 | `../../../USalign/USalign.cpp`（主入口）及全部 `.h` 头文件 |
| Git 分支 | `master`（原始基线）+ `USalign-beta`（修改版，51 commits 领先 master） |

## 8. 关联文档

| 文档 | 路径 | 内容 |
|------|------|------|
| Claude Code 指导 | `CLAUDE.md` | 快速参考：常用命令、架构说明、约定 |
| 重构总体方案 | `docs/superpowers/specs/2026-05-12-usalign-cpp-refactor-design.md` | 22 类 C→C++ 映射、4 层文件拆分、独立里程碑、风险控制 |
| 重构进度日志 | `docs/superpowers/specs/2026-05-14-refactor-progress-log.md` | 逐日逐步记录、24 个问题发现与修复、51 commit 链路 |
| 最终总结 | `docs/superpowers/specs/2026-05-21-refactor-final-summary.md` | 完成状态、剩余工作、已验证测试结果（含终态目录图） |
| L2-h 二级指针方案 | `docs/superpowers/specs/2026-05-21-usalign-l2h-pointer-to-container-design.md` | ~347 处二级指针 → C++ 容器，~38 步详细方案 |
| USalign 源码架构 | `../../../USalign/` 和 `../mm1/CLAUDE.md` | 源码结构、算法流程、文件清单、命令行选项 |

## 9. 已知限制

1. Windows 原生编译不支持 `.gz`/`.bz2` 压缩文件（`pstream.h` 依赖 POSIX pipe）
2. 性能测试可能因系统负载产生自然波动，`20%-50%` 的 WARNING 需人工判定
3. 独立程序（TMscore/HwRMSD/MMalign/pdb2ss）的测试不在 `run_regression.py` 覆盖范围内，需单独运行 `standalone/<程序>/run_test.py`
4. 远程仓库断开时，`USalign-beta` 分支可能无法 push（当前已解决，51 commits 已推送到 origin）
