# cLanguage2Cplus — USalign C→C++ 重构 回归与性能测试框架

## 1. 概述

本目录是 **USalign** 的回归与性能测试框架。USalign 是一款通用的蛋白质/核酸结构比对工具。`master` 基线仍从单文件 `../../../USalign/USalign.cpp` 编译；`USalign-beta` 已拆分为 `../../../USalign/src/` 下的多文件 C++ 工程，主入口为 `src/app/usalign/usalign.cpp`。

> **目录布局要求**：`usalign-refactor-tests-framework/` 必须与 `USalign/` 源码目录放在同一级目录下，所有脚本中的相对路径（`../../../USalign/`）依赖此布局。

本框架的核心目的是验证 `USalign-beta` 相对 `master` 基线的功能兼容性、并行确定性和性能。分支提交数量会持续变化，因此以当前 Git 历史和测试用例文件为准，不在本文固定记录提交数。

## 2. 目录层级结构

### 2.1 总体层级

```
<workspace>/                        # 工作区根目录
├── USalign/                        # 源码仓库（master / USalign-beta）
└── usalign-refactor-tests-framework/  # 测试框架仓库 (main)
    └── scripts/
        ├── cLanguage2Cplus/        # ★ 本目录 — 主回归测试框架
        ├── mm1/                    # MMalign 独立功能测试
        ├── upgmatree/              # MSTA / UPGMA 测试
        ├── chainmap_local/          # -chainmap 局部约束测试
        ├── flexalign/               # FlexAlign 测试
        └── usalign_full/            # 统一回归入口
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
│   ├── run_regression.py               # 编译 USalign-beta 修改版 → 比对 40 个功能用例
│   ├── create_perf_baseline.py         # 编译 master 原始版 → 生成性能基线 perf_baseline/
│   ├── run_perf_test.py                # 编译 USalign-beta 修改版 → 性能测试 (5次取平均)
│   ├── build_Small_DB.py               # 从 PDB 库随机抽取 100 个结构构建 smallDB
│   └── find_pdb_length.py              # 辅助工具 — 统计 PDB 文件残基数
│
├── 测试用例定义 (纯文本, 每行一个用例)
│   ├── testcases_functional.txt        # 40 个功能回归用例 (格式: <name> <workdir> <args...>)
│   └── testcases_performance.txt       # 5 个性能回归用例
│
├── baseline/                           # 原始版基线 — 40 个 .out + sup.pdb (create_baseline.py 生成)
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
│   │   ├── US735192405.pdb ~ US73519240510.pdb  # 11 个 RNA 结构
│   │   └── list.txt                    #   文件列表
│   └── smallDB/                         # 数据库搜索子集 (100 个随机 PDB + list.txt)
│
├── standalone/                          # ★ 17 个独立程序子测试框架
│   ├── tmscore/                         # TMscore: 6 用例 (help目录下的全部示例)
│   │   ├── testcases.txt               #   用例定义
│   │   ├── create_baseline.py          #   从 master 提取 TMscore.cpp → 编译 → 生成基线
│   │   └── run_test.py                 #   编译 USalign-beta 源码 → 归一化后比对
│   ├── hwrmsd/                          # HwRMSD: 5 用例
│   │   ├── testcases.txt
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   ├── mmalign/                         # MMalign: 4 用例
│   │   ├── testcases.txt
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   ├── pdb2ss/                          # pdb2ss: 2 用例
│   │   ├── testcases.txt
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   ├── pdbatomname/                     # pdbAtomName: 5 用例 (9 次比对, 含 out.pdb)
│   │   ├── testcases_baseline.txt       #   master 用例 (无 -outdir)
│   │   ├── testcases.txt                #   beta 用例 (run_test.py 追加 -outdir .)
│   │   ├── create_baseline.py
│   │   └── run_test.py
│   ├── addchainid/                      # addChainID: 8 用例 (14 次比对, 含 out.pdb)
│   ├── xyz_sfetch/                      # xyz_sfetch: 7 用例 (9 次比对, 含 .index)
│   ├── tmalign/                         # TMalign: 8 用例 (10 次比对, 含 sup.pdb/matrix.txt)
│   ├── se/                              # se: 4 用例 (仅 stdout)
│   ├── nwalign/                         # NWalign: 6 用例 (仅 stdout)
│   ├── qtmclust/                        # qTMclust: 5 用例 (7 次比对, 含 cluster.txt)
│   ├── pdb2xyz/                         # pdb2xyz: 5 用例 (仅 stdout)
│   ├── pdb2fasta/                       # pdb2fasta: 5 用例 (仅 stdout)
│   ├── biounitasym/                     # biounitasym: 4 用例 (仅 stdout)
│   ├── cif2pdb/                         # cif2pdb: 5 用例 (9 次比对, 含 out*.pdb)
│   ├── usalign/                         # USalign: 21 用例 (22 次比对, 含 sup.pdb)
│   └── usflexalign/                     # USFlexalign: 13 用例 (26 次比对, 含 matrix/spt/cxc/sup.pdb)
│
├── docs/superpowers/specs/              # ★ 项目设计与分析文档
│   ├── 2026-05-12-usalign-cpp-refactor-design.md         # 重构总体方案
│   ├── 2026-05-14-refactor-progress-log.md               # 重构详细进度日志
│   ├── 2026-05-21-refactor-final-summary.md              # 最终总结
│   └── 2026-05-21-usalign-l2h-pointer-to-container-design.md  # 二级指针→容器方案
│
├── USalign_orig[.exe]                  # 原始版可执行文件（.exe 仅 Windows）
└── __pycache__/                        # Python 缓存
```

## 3. 快速开始

**前置条件**：
- C++11 编译器可编译 USalign；当前 beta 回归脚本还固定使用 OpenMP（`-fopenmp`）
- Python 3.6+
- 本目录下的 `.py` 脚本**必须在本目录内运行**

macOS 自带的 `/usr/bin/g++` 实际是 Apple Clang。USalign-beta 源码现可用 Apple Clang 执行 `make OPENMP=0` 串行构建，但当前回归脚本固定传入 GCC 风格的 `-fopenmp`。运行这些并行回归脚本时仍建议安装 Homebrew GCC，并确保脚本调用到带版本号的 GNU 编译器；当前验证环境使用 `/opt/homebrew/bin/g++-16`。

### 3.1 建立基线（修改源码前，仅执行一次）

```bash
cd cLanguage2Cplus

# 1. 生成功能基线 — 从 master 编译 USalign，执行 40 个用例（单线程），保存输出到 baseline/
python create_baseline.py

# 2. 生成性能基线 — 从 master 编译 USalign，5 个用例各跑 5 次（单线程），保存到 perf_baseline/baseline.csv
python create_perf_baseline.py
```

> 基线用例集（`testcases_baseline_functional.txt`、`testcases_baseline_performance.txt`）与回归用例集的主要区别是**不使用 `-threads` 参数**，即单线程运行。回归用例集（`testcases_functional.txt`、`testcases_performance.txt`）包含 `-threads` 参数，用于测试多线程并行加速的正确性。两者分别使用不同的用例配置文件，互不干扰。

### 3.2 开发迭代（修改源码后，反复执行）

```bash
cd cLanguage2Cplus

# 1. 运行功能回归 — 从 USalign-beta 多文件源码编译并比对 40 个用例
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
| **用途** | 生成回归测试的黄金标准输出（单线程） |
| **编译源** | `master` 分支的 `../../../USalign/USalign.cpp` |
| **产物** | `USalign_orig[.exe]` + `baseline/` 目录（40 个 `.out` + `sup.pdb`，`.exe` 仅 Windows） |
| **输入** | `testcases_baseline_functional.txt`（不含 `-threads` 参数） |
| **执行时机** | 修改源码前**仅执行一次** |
| **工作原理** | 自动 checkout → `master`，编译原始单文件版本，逐条执行 40 个用例，捕获 stdout+stderr，经 `clean_slash()` 清洗后保存到 `baseline/` |
| **与回归的区别** | 基线使用 `testcases_baseline_functional.txt`（单线程），回归使用 `testcases_functional.txt`（多线程 `-threads 2/4`） |

### 4.2 `run_regression.py` — 功能回归测试

| 项目 | 说明 |
|------|------|
| **用途** | 验证修改版输出与基线在既定归一化规则下一致 |
| **编译源** | `USalign-beta` 分支的 `../../../USalign/src/` 多文件源码 |
| **产物** | `USalign_mod_<pid>[.exe]` + `current/`（40 个 `_mod.out`）+ `diffs/`（差异文件；`.exe` 仅 Windows） |
| **输入** | `testcases_functional.txt` + `baseline/` |
| **执行时机** | 每次修改源码后 |
| **输出判定** | `PASS` = 归一化后完全一致 / `WARNING` = 仅非业务差异 / `FAIL` = 业务输出或串并行检查不一致 / `ERROR` = 文件缺失 |
| **特殊处理** | 所有带 `-threads` 的用例额外做并行重复运行和串行/并行一致性检查；`superposed_structure` 额外逐字节比对 `sup.pdb`；自动清理 `.pml`；文本输出清理路径斜杠和 CPU 时间 |
| **注意** | 每次运行前自动清空 `current/` 和 `diffs/` 目录 |

### 4.3 `create_perf_baseline.py` — 性能基线生成

| 项目 | 说明 |
|------|------|
| **用途** | 生成性能参考基线（单线程） |
| **编译源** | `master` 分支 |
| **产物** | `USalign_orig[.exe]` + `perf_baseline/baseline.csv`（`.exe` 仅 Windows） |
| **输入** | `testcases_baseline_performance.txt`（不含 `-threads` 参数） |
| **参数** | 每个用例运行 **5 次**，使用 Python `time.perf_counter()` 测量单调墙钟时间并取平均值 |
| **执行时机** | 修改源码前仅执行一次 |
| **与回归的区别** | 基线使用 `testcases_baseline_performance.txt`（单线程），回归使用 `testcases_performance.txt`（多线程 `-threads 2/4`） |

### 4.4 `run_perf_test.py` — 性能回归测试

| 项目 | 说明 |
|------|------|
| **用途** | 检测修改是否引入性能退化 |
| **编译源** | `USalign-beta` 分支 |
| **产物** | `USalign_mod_<pid>[.exe]` + `perf_current/performance.csv`（`.exe` 仅 Windows） |
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

`standalone/` 下共 17 个套件，覆盖全部 17 个可执行程序。每个套件含两个核心脚本：

**`create_baseline.py`**：从 `master` 分支提取独立程序的 `.cpp` 源码 → 编译 → 执行用例 → 保存基线输出到 `baseline/`

**`run_test.py`**：切换到 `USalign-beta` → 编译独立程序 → 执行用例 → 归一化文本后比对基线。

**双用例文件**：13 个较新的套件（`pdbatomname`、`addchainid`、`xyz_sfetch`、`tmalign`、`se`、`nwalign`、`qtmclust`、`pdb2xyz`、`pdb2fasta`、`biounitasym`、`cif2pdb`、`usalign`、`usflexalign`）使用两份用例：

- `testcases_baseline.txt`：给 `create_baseline.py` 用。master 分支没有 `-outdir` 选项，参数按原样传入，因此只能用 master 也接受的写法（例如 master 的 PyMOL 选项是 `-o`，beta 才是 `-pymol`）。
- `testcases.txt`：给 `run_test.py` 用，会追加 `-outdir .`（已自带 `-outdir` 的用例除外），使输出文件落在用例工作目录内，便于收集比对。

早期 4 个套件（`tmscore`、`hwrmsd`、`mmalign`、`pdb2ss`）只有一份 `testcases.txt`。

**产物比对**：除 stdout/stderr 外，还逐字节比对用例生成的文件：

| 套件 | 比对产物 |
|------|----------|
| `pdbatomname` / `addchainid` | `out.pdb` |
| `xyz_sfetch` | `.index` 索引文件 |
| `tmalign` | `sup.pdb`、`matrix.txt` |
| `qtmclust` | `cluster.txt` |
| `cif2pdb` | `out*.pdb`（`-split 1` 会生成 `out.pdb<chain>.pdb`） |
| `usalign` | `sup.pdb` |
| `usflexalign` | `matrix.txt`、`*.spt`、`*.cxc`、`sup.pdb` |

`se`、`nwalign`、`pdb2xyz`、`pdb2fasta`、`biounitasym` 只写 stdout，无比对产物。

**`normalize()` 归一化**：比对前统一处理以下差异，避免把非行为差异误判为回归：

- 可执行文件路径 → `EXE`（master 与 beta 的可执行文件名不同）；
- 用例工作目录前缀 → 去掉（绝对/相对路径差异）；
- `#Total CPU time` 或 `#Total elapsed time` 行 → 删除（计时结果自然波动）；
- 10 位以上小数 → 四舍五入到 6 位（重构改变了浮点归约顺序，末位差 1 ULP，与 `-O3` 无关）；
- `-0.000000` → `0.000000`，并把纯数字行（旋转矩阵）的列间距压成单空格（去掉零的负号会使字段变短）；
- `# Chain pairing summary` 及其 `Protein:`/`RNA:`/`Chainmap:`/`Unpaired:` 续行 → 删除（beta 新增的配对汇总输出）。

**未纳入 `usalign` 套件的模式**：`-mm 4`（MSTA）与 `-chainmap`。beta 为 `-mm 4` 增加了 UPGMA 树、`ccTM-score` 行，且成对比较顺序不同；`-chainmap` 会打印完整链 ID。这两类行为由 `scripts/chainmap_local/` 与 `cLanguage2Cplus/testcases_functional.txt` 覆盖。

**`xyz_sfetch` 的顺序依赖**：`no_index` 必须在 `index` 之前，"建索引" 必须在各 "取子集" 之前；脚本会在每个用例前后清理索引文件，只对比本用例真正产生（新增或内容改变）的产物。


## 5. 测试用例说明

### 5.1 用例格式

```
<用例名称> <工作目录> <USalign 命令行参数...>
```

- `<工作目录>` **相对于 `data/` 目录**，用 `.` 表示 data 根目录
- 以 `#` 开头的行是注释
- 脚本执行 USalign 前会将 `cwd` 设为 `data/<工作目录>`

### 5.2 功能测试用例（40 个）

完整命令以 `testcases_functional.txt` 为唯一事实来源。当前 40 个用例按覆盖范围分组如下：

| 分组 | 用例 | 主要覆盖 |
|------|------|----------|
| 基础与主模式（15） | `standard_protein`、`multichain_split`、`oligomer`、`circular_permutation`、`circular_permutation_restore`、`fully_non_seq`、`semi_non_seq`、`superposed_structure`、`tmscore_resid`、`tmscore_seqalign`、`complex_chainid`、`complex_chainmap`、`msta_rna`、`all_vs_all`、`database_search` | 单体、多链、循环置换、非顺序、TM-score、MSTA、数据库搜索及结构文件输出 |
| MMdock / `-mm 2`（3） | `mmdock`、`mm2_trim_serial`、`mm2_trim_parallel` | 多链 docking、短链裁剪、批量并行一致性 |
| `-mm 1` 与 chainmap（7） | `chainmap_full`、`dimer_mm1`、`mm1_with_o`、`mm1_with_se`、`mm1_with_se_lowscore`、`mm1_symwrite_guard`、`mm1_hetero_asym` | 完整链映射、二聚体、结构输出、低分保护、异质复合物 |
| 目录批量与非顺序模式（7） | `mm0_se_dir2`、`mm0_cp_dir2`、`mm5_dir2`、`mm6_dir2`、`mm5_dir`、`mm0_mirror_dir2`、`mm7_dir` | `-dir`/`-dir2`、`-se`、CP、镜像、`-mm 5/6/7` |
| 输出格式（2） | `mm1_se_outfmt1`、`mm1_se_outfmt2` | `-mm 1 -se` 的 FASTA/表格输出 |
| mmCIF 与完整链 ID（6） | `mm0_cif_dataprefix`、`mm_cif_multichar_tmscore2`、`mm_cif_multichar_tmscore3`、`mm_cif_singlechar_tmscore2`、`mm_cif_singlechar_tmscore3`、`mm_cif_byresi3_multichar` | data_ 前缀、多字符/单字符链 ID、`-TMscore 2/3` |

> **说明**：`-outfmt -1` 表示完整输出（不含版本横幅）；`-m -` 将旋转矩阵输出到 stdout。回归用例通过 `-threads 4` 覆盖并行路径，脚本还会自动执行重复并行和单线程交叉检查。

### 5.3 性能测试用例（5 个）

| # | 用例名 | 工作目录 | 测试场景 |
|---|--------|----------|----------|
| 1 | `perf_fast1` | `.` | 快速蛋白比对 |
| 2 | `perf_fast2` | `.` | 快速蛋白比对 |
| 3 | `perf_msta_rna` | `MSTATest` | RNA 多结构比对 |
| 4 | `perf_database_search` | `smallDB` | 批量数据库搜索 |
| 5 | `perf_mmdock` | `mmdock` | `-mm 2` 批量 docking |

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
       └────── 按既定规则比较 ─────┘
                    │
       PASS / WARNING / FAIL (diff)
```

两个可执行文件来自同一仓库的不同分支，但源码布局不同：
- **原始版** = `master` 分支的单文件 `USalign.cpp`
- **修改版** = `USalign-beta` 分支的 `src/` 多文件源码

### 6.2 输出比对逻辑

`run_regression.py` 对文本输出进行归一化后的精确比对，并对结构文件逐字节比对：

1. 捕获 USalign 的 `stdout + stderr`，调用 `clean_slash()` 统一已知路径前缀，并移除自然波动的 `#Total CPU time` 或 `#Total elapsed time` 行。
2. 精确比较归一化后的基线文本和当前文本；不一致时生成 `diffs/<用例名>.diff`。
3. 对每个含 `-threads` 的功能用例重复运行一次并行命令，再运行 `-threads 1`，检查并行确定性和串并行一致性。
4. `superposed_structure` 生成的 `sup.pdb` 使用逐字节比较。

主回归脚本有意保持严格：除路径斜杠和 CPU 时间外，浮点末位、`-0.0`、新增摘要等变化仍会形成 diff 并报告 `FAIL`，需要结合差异内容判断是否属于预期行为。`standalone/` 套件采用更宽松的 `normalize()` 规则。

### 6.3 关键约定

- baseline 输出文件命名为 `<用例名>.out`，修改版追加 `_mod` 后缀（如 `standard_protein_mod.out`）
- `superposed_structure` 额外比对生成的 `sup.pdb` 结构文件
- `current/`、`diffs/`、`perf_current/` 每次运行时自动清空重建，**切勿在其中存放重要文件**
- Windows 下 `-dir` / `-dir2` 使用反斜杠路径分隔符 (`.\`)
- 测试完成后自动恢复到运行前的 Git 分支

## 7. 依赖与编译

| 项目 | 说明 |
|------|------|
| 编译器 | GNU `g++`，需要 `-O3 -ffast-math -fopenmp`；Windows 追加静态运行库选项 |
| Python | 3.6+，仅使用标准库 (`subprocess`, `difflib`, `csv`, `pathlib`, `shutil`, `re`) |
| USalign 源码 | master：`../../../USalign/USalign.cpp`；beta：`../../../USalign/src/` 多文件源码 |
| Git 分支 | `master`（原始基线）+ `USalign-beta`（修改版） |

### 7.1 多线程支持说明

USalign 主程序支持 OpenMP 多线程加速，通过以下方式启用：

- **编译时**：使用 `OPENMP=auto` 时，Makefile 仅在目标编译器通过探测后添加 `-fopenmp`；也可用 `OPENMP=0` 主动关闭
- **运行时**：通过 `-threads N` 参数指定线程数，如 `-threads 4`

支持 `-threads` 的批量模式：`-dir`、`-dir1`、`-dir2`、`-dirpair`

> **注意**：只有 `USalign` 支持 `-threads N`。`standalone/` 下的 17 个套件编译各自的独立程序，不使用该命令行选项，编译时也无需 `-fopenmp`。

## 8. 关联文档

| 文档 | 路径 | 内容 |
|------|------|------|
| Claude Code 指导 | `CLAUDE.md` | 快速参考：常用命令、架构说明、约定 |
| 重构总体方案 | `docs/superpowers/specs/2026-05-12-usalign-cpp-refactor-design.md` | C→C++ 映射、文件拆分、里程碑与风险控制 |
| 重构进度日志 | `docs/superpowers/specs/2026-05-14-refactor-progress-log.md` | 重构过程、问题发现与修复记录 |
| 最终总结 | `docs/superpowers/specs/2026-05-21-refactor-final-summary.md` | 完成状态、剩余工作、已验证测试结果（含终态目录图） |
| L2-h 二级指针方案 | `docs/superpowers/specs/2026-05-21-usalign-l2h-pointer-to-container-design.md` | ~347 处二级指针 → C++ 容器，~38 步详细方案 |
| USalign 源码架构 | `../../../USalign/` 和 `../mm1/CLAUDE.md` | 源码结构、算法流程、文件清单、命令行选项 |

## 9. 已知限制

1. Windows 原生编译不支持 `.gz`/`.bz2` 压缩文件（`pstream.h` 依赖 POSIX pipe）
2. 性能测试可能因系统负载产生自然波动，`20%-50%` 的 WARNING 需人工判定
3. 独立程序（TMscore/HwRMSD/MMalign/pdb2ss/pdbAtomName/addChainID/xyz_sfetch/TMalign/se/NWalign/qTMclust/pdb2xyz/pdb2fasta/biounitasym/cif2pdb/USalign/USFlexalign）的测试不在 `run_regression.py` 覆盖范围内，需单独运行 `standalone/<程序>/run_test.py`
4. Apple Clang 可用 `make OPENMP=0` 构建 USalign-beta，但当前并行回归脚本仍要求 OpenMP；运行这些脚本时应使用 Homebrew GCC，或自行配置 Clang + libomp
