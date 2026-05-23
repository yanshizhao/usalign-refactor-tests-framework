# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 构建

```bash
make              # 构建所有可执行文件（USalign, TMalign, TMscore, MMalign, se 等）
make USalign      # 仅构建主程序
make clean        # 删除所有已构建的可执行文件
```

编译器：g++，使用 `-O3 -ffast-math`。Mac OS 上需去掉 `-static` 标志。也支持 clang++ >= 12.0.5 和 mingw-w64 >= 9.3。

Windows 原生编译（无 WSL）：
```bash
make USalign.exe  # 使用 x86_64-w64-mingw32-g++ -static
```

本仓库没有测试。

## 项目概述

US-align 是一个通用的蛋白质和核酸结构比对工具，支持单体、寡聚体、循环排列、序列无关比对和柔性比对等多种模式。主要算法基于 TM-align，扩展了 RNA/DNA 比对（RNA-align）、寡聚体比对（MM-align）和多结构比对（MSTA）等功能。

**主要特性**：
- 支持蛋白质和 RNA/DNA 的结构比对
- 自动检测分子类型
- 支持多种比对模式（单体、寡聚体、循环排列、多结构、序列无关等）
- 支持 PDB、PDBx/mmCIF、SPICKER 格式输入
- 支持 gzip/bzip2 压缩文件（仅 Linux/Mac/WSL2）
- 支持 PyMOL、RasMol、ChimeraX 格式输出

**版本**：Version 20260329

**文献**：
- C Zhang, L Freddolino, Y Zhang. (2026) Nat Protoc. 21, 517-541.
- C Zhang, M Shine, AM Pyle, Y Zhang. (2022) Nat Methods. 19(9), 1109-1115.
- C Zhang, AM Pyle (2022) iScience. 25(10), 105218.

## 架构

这是一个纯头文件 C++ 代码库。每个可执行文件从单个 `.cpp` 编译，通过 `#include` 引入所有 `.h` 头文件中的逻辑，没有独立的编译单元或共享对象文件。

### 完整文件清单（21 个源文件）

**核心算法头文件：**
| 文件 | 行数 | 用途 |
|------|------|------|
| `TMalign.h` | ~3,800 | 核心单体比对引擎。包含 `TMalign_main()`、`score_fun8()`、`TMscore8_search()`、二级结构分配（`make_sec` 蛋白质/RNA）、`DP_iter()`、所有结果格式化 |
| `MMalign.h` | ~3,000 | 寡聚体比对：全对全链 TM-score → 贪心链分配 → 质心优化 → 迭代重比对。含 `enhanced_greedy_search`、`homo_refined_greedy_search`、`hetero_refined_greedy_search`、`MMalign_iter` |
| `SOIalign.h` | ~900 | 序列顺序无关比对（`-mm 5` 完全非序列，`-mm 6` 半非序列）。使用 K 近邻原子初始化 + 增强贪心搜索（`soi_egs`） |
| `flexalign.h` | ~2,000 | 柔性比对（`-mm 7`），允许多个铰链点。先运行 TMalign，再在铰链处分段叠合。`flexalign_main()` 为入口函数 |
| `NWalign.h` | ~600 | 完整 Gotoh 算法序列比对（支持 gap_open ≠ gap_extend），含 BLOSUM62/BLASTN 矩阵，支持全局/半全局/局部模式（`glocal=0/1/2/3`） |
| `NW.h` | 436 | 简化版 Needleman-Wunsch 动态规划（gap_open = gap_extend，无 Gotoh）。三种变体：`NWDP_TM`（预计算分数矩阵）、`NWDP_TM`（带旋转的坐标输入）、`NWDP_SE`（无旋转，纯结构评分）、`NWDP_SE`（带 hinge 约束） |
| `Kabsch.h` | 334 | 通过协方差矩阵特征值分解求解最优旋转矩阵和平移向量。`Kabsch()` 支持三种模式：仅 RMSD、仅旋转矩阵、两者都算 |
| `se.h` | 241 | 无叠加的纯结构比对（`-se` 选项）。`se_main()` 使用 `NWDP_SE()` 基于距离做 NW 动态规划，不做 Kabsch 旋转迭代 |
| `param_set.h` | 78 | d0 归一化公式。`parameter_set4search()`：蛋白质 `d0 = 1.24*(L-15)^(1/3) - 1.8`；`parameter_set4final()`：区分蛋白质和 RNA；`parameter_set4final_C3prime()`：RNA 使用 C3' 原子的分段 d0 公式 |

**基础/工具头文件：**
| 文件 | 行数 | 用途 |
|------|------|------|
| `basic_fun.h` | 1,051 | 文件解析（PDB/mmCIF/SPICKER/FASTA/xyz）、几何运算（`dist`、`dot`、`transform`、`do_rotation`）、字符串工具、`NewArray`/`DeleteArray` 模板、用户比对读取 |
| `BLOSUM.h` | ~1,300 | BLOSUM62、BLOSUM80、BLOSUM45、BLASTN 替换矩阵的静态数据 |
| `pstream.h` | ~1,800 | 第三方库，通过管道调用 `gunzip`/`bzcat` 读取压缩文件 |

**可执行文件入口点（.cpp 文件）：**
| 文件 | 编译产物 | 用途 |
|------|----------|------|
| `USalign.cpp` | `USalign` | **主程序**。3,608 行。`main()` 解析命令行参数，通过 `-mm` 选项统一调度所有比对模式。含 `TMalign()`、`MMalign()`、`MMdock()`、`mTMalign()`、`SOIalign()`、`flexalign()` 等顶层函数 |
| `TMalign.cpp` | `TMalign` | 独立的单体蛋白比对工具（精简版 USalign） |
| `TMscore.cpp` | `TMscore` | 纯 TM-score/GDT/MaxSub 计算（不做结构比对），含 `-c` 寡聚体模式 |
| `MMalign.cpp` | `MMalign` | 独立的寡聚体比对工具 |
| `se.cpp` | `se` | 独立的结构比对提取工具 |
| `qTMclust.cpp` | `qTMclust` | 准 TM-score 聚类工具 |
| `NWalign.cpp` | `NWalign` | 独立的序列比对工具 |
| `HwRMSD.cpp` | `HwRMSD` | 加权 RMSD 计算（Hung & Weng 方法） |

**工具程序：**
| 文件 | 编译产物 | 用途 |
|------|----------|------|
| `pdb2xyz.cpp` | `pdb2xyz` | PDB 转 xyz 格式 |
| `xyz_sfetch.cpp` | `xyz_sfetch` | 从 xyz 数据库中提取结构 |
| `pdb2fasta.cpp` | `pdb2fasta` | PDB 转 FASTA 序列 |
| `pdb2ss.cpp` | `pdb2ss` | 提取二级结构 |
| `cif2pdb.cpp` | `cif2pdb` | mmCIF 转 PDB 格式 |
| `pdbAtomName.cpp` | `pdbAtomName` | 标准化 PDB 原子名称 |
| `addChainID.cpp` | `addChainID` | 为无链 ID 的 PDB 添加链 ID |
| `biounitasym.cpp` | `biounitasym` | 生物单元与不对称单元转换 |

**其他文件：** `__init__.py`（PyMOL 插件），`Dockerfile`（多阶段构建，gcc:12.2 → ubuntu:latest），`Makefile`

### 头文件依赖链

```
USalign.cpp
 ├── MMalign.h       → se.h → TMalign.h → NWalign.h → NW.h → Kabsch.h → param_set.h → basic_fun.h
 ├── SOIalign.h      → TMalign.h（同上链路）
 └── flexalign.h     → TMalign.h（同上链路）
```

`BLOSUM.h` 和 `pstream.h` 是独立的数据/工具头文件，分别被 `basic_fun.h` 和 `NWalign.h` 引入。

### TMalign_main() 核心算法流程（TMalign.h:3138）

1. **参数初始化**：调用 `parameter_set4search()` 设置 D0_MIN、Lnorm、d0、d0_search、score_d8

2. **多策略初始比对**（按顺序尝试，每种策略后都跟 DP_iter 迭代优化）：

   | 顺序 | 策略 | 函数 | 说明 |
   |------|------|------|------|
   | 1 | Gapless threading | `get_initial()` | 滑动窗口找最优偏移量，每个偏移量做 3 轮快速 Kabsch 迭代 |
   | 2 | 二级结构比对 | `get_initial_ss()` | 对 DSSP 二级结构字符做 NW 动态规划 |
   | 3 | 局部叠加 | `get_initial5()` | 取局部片段 → Kabsch 旋转 → 扩展匹配区域，类似 TMalign Fortran |
   | 4 | SS + 局部叠加 | `get_initial_ssplus()` | 结合二级结构和结构叠加的混合策略 |
   | 5 | 片段 gapless threading | `get_initial_fgt()` | 用多个小片段做 gapless threading 叠加 |

3. **TMcut 预终止**：每个策略后检查 TM-score 是否可能达到阈值（阈值从 0.5 逐步提升到 0.6），如果无望则提前返回

4. **详细搜索**：`detailed_search()` → `TMscore8_search()` 做 20 轮迭代优化，逐步缩小 fragment 大小（Lali → Lali/2 → Lali/4 → ... → 4）

5. **DP 迭代**：`DP_iter()` 进行 NW 动态规划 + Kabsch 旋转的迭代循环

6. **最终 TM-score 计算**：
   - 用 `parameter_set4final()` 设置输出 d0
   - 筛选距离 ≤ score_d8 的残基对
   - 对这些残基对重新 Kabsch 计算 RMSD
   - 分别按结构 A 长度（TM1）、结构 B 长度（TM2）、平均长度（TM3，-a）、自定义长度（TM4，-u）、自定义 d0（TM5，-d）归一化

7. **输出对齐序列**：生成 seqxA/seqyA/seqM 字符串，标记 `:`（d < d0）和 `.`（d ≥ d0）

### USalign.cpp `main()` 中的调度

`-mm` 选项选择比对模式，每个模式路由到顶层函数：

| `-mm` | 函数 | 用途 |
|-------|------|------|
| 0 | `TMalign()` | 单体比对（也处理 `-cp` 和 `-mirror`） |
| 1 | `MMalign()` | 寡聚体比对 |
| 2 | `MMdock()` | 链到寡聚体比对 |
| 3 | `TMalign()` 且 `cp_opt=true` | 循环排列比对 |
| 4 | `mTMalign()` | 多结构比对（MSTA） |
| 5/6 | `SOIalign()` | 非序列比对 |
| 7 | `flexalign()` | 柔性比对 |

每个顶层函数遵循相同模式：解析PDB → 分配坐标数组 → 调用比对引擎 → 输出结果 → 释放内存。

### MMalign 寡聚体比对流程（MMalign.h）

1. 解析两个复合物的所有链
2. 对每对链运行 `TMalign_main()` 计算全对全 TM-score 矩阵
3. `enhanced_greedy_search()` — 贪心链分配
4. 对三聚体及以上：`homo_refined_greedy_search()` + `hetero_refined_greedy_search()` — 基于质心叠加的贪心搜索优化
5. 对二聚体：`adjust_dimer_assignment()` — 检查交换链分配是否改善分数
6. `MMalign_iter()` — 迭代优化：逐链重新比对到对方复合物的剩余链

### 关键数据模式

- **坐标**：`double **xa`（通过 `NewArray`/`DeleteArray` 模板管理的2D原始指针数组）。寡聚体使用 `vector<vector<vector<double>>>` 存储逐链坐标。
- **序列/二级结构**：`char *seqx`、`char *secx`（C风格，null终止）。
- **比对映射**：`int *invmap`，其中 `invmap[j]` = 与结构y中位置j对齐的结构x中的索引（-1 = 间隙）。
- **内存管理**：全部手动分配/释放（`new[]`/`delete[]` + `NewArray`/`DeleteArray`），无智能指针。

### 关键函数签名与位置

| 函数 | 文件:行号 | 用途 |
|------|-----------|------|
| `score_fun8()` | TMalign.h:13 | TM-score = Σ 1/(1+di²/d0²)/Lnorm，同时筛选 di < d 的残基 |
| `TMscore8_search()` | TMalign.h:101 | 多尺度局部片段叠加搜索最优旋转矩阵，最多 20 轮迭代 |
| `detailed_search()` | TMalign.h:416 | 包装 TMscore8_search，从 invmap 提取对齐坐标 |
| `get_initial()` | TMalign.h:642 | Gapless threading 初始比对 |
| `get_initial5()` | TMalign.h:943 | 局部结构叠加初始比对（初始5） |
| `get_initial_ss()` | TMalign.h:928 | 二级结构初始比对 |
| `get_initial_fgt()` | TMalign.h | 片段 gapless threading |
| `get_initial_ssplus()` | TMalign.h | 二级结构+局部叠加混合 |
| `DP_iter()` | TMalign.h | NW 动态规划 + Kabsch 旋转迭代 |
| `TMalign_main()` | TMalign.h:3138 | 核心单体比对入口 |
| `se_main()` | se.h:8 | 纯结构比对（不做叠加），使用 NWDP_SE |
| `make_sec()` (蛋白质) | TMalign.h:767 | 基于 Cα 距离的 DSSP 风格二级结构分配 |
| `make_sec()` (RNA) | TMalign.h:823 | 基于碱基配对检测的 RNA 二级结构分配 |
| `Kabsch()` | Kabsch.h:14 | 最优旋转矩阵求解 |
| `NWDP_TM()` | NW.h:17 | 简化 NW 动态规划（gap_open = gap_extend） |
| `NWDP_SE()` | NW.h:186 | 基于结构距离的 NW 动态规划 |
| `calculate_score_gotoh()` | NWalign.h:103 | 完整 Gotoh 算法（gap_open ≠ gap_extend） |
| `get_PDB_lines()` | basic_fun.h:152 | PDB/mmCIF/SPICKER 文件解析 |
| `read_PDB()` | basic_fun.h:770 | 从 PDB 文本行提取坐标和序列 |
| `enhanced_greedy_search()` | MMalign.h:198 | 寡聚体链配对贪心搜索 |
| `soi_egs()` | SOIalign.h:116 | 序列无关比对的增强贪心搜索 |
| `flexalign_main()` | flexalign.h:48 | 柔性比对入口 |

### 输入/输出

- **输入格式**：PDB、PDBx/mmCIF（自动检测）、SPICKER。Linux/Mac 上通过 `pstream.h`（管道调用 `gunzip`/`bzcat`）支持 gzip/bz2 压缩文件。Windows 原生不支持压缩文件。
- **输出格式**：完整文本（`-outfmt 0`）、FASTA（`1`）、表格（`2`）。叠合输出为 PyMOL（`-o`）、RasMol（`-rasmol`）或 ChimeraX（`-chimerax`）脚本。
- **PyMOL 插件**：`__init__.py` 封装 USalign 二进制文件供 PyMOL 内部使用。提供 `usalign` 和 `usalign_msta` 两个命令。

### 分子类型

`mol_vec[i] > 0` 表示 RNA/DNA 链；`mol_vec[i] <= 0` 表示蛋白质链。支持蛋白质-RNA混合复合物，但蛋白质链和RNA链不会互相比对。`-mol` 选项可将所有链强制设为同一类型。

### Docker 构建

多阶段构建：第一阶段 `gcc:12.2` 编译并 strip 二进制文件，第二阶段 `ubuntu:latest` 仅复制最终可执行文件到 `/usr/bin/usalign/`。

## 命令行选项详解

### 核心选项

| 选项 | 用途 | 默认值 |
|------|------|--------|
| `-mol` | 分子类型：auto/prot/RNA | auto |
| `-mm` | 比对模式（0-7） | 0 |
| `-ter` | 链数量：0（所有链）、1（第一个模型的链）、2（仅第一条链）、3（TER 分割） | 2 |
| `-TMscore` | TM-score 叠加：0（独立）、1（残基索引）、2（残基索引+链ID）、5（glocal 序列）、6（链映射+残基ID）、7（全局序列+链映射） | 0 |

### 输入输出选项

| 选项 | 用途 |
|------|------|
| `-infmt1`, `-infmt2` | 输入格式：-1（自动）、0（PDB）、1（SPICKER）、3（mmCIF） |
| `-chain1`, `-chain2` | 指定比对的链（逗号分隔） |
| `-model1`, `-model2` | 指定模型（逗号分隔） |
| `-split` | 分割方式：0（单链）、1（按模型）、2（按链） |
| `-outfmt` | 输出格式：0（完整）、1（FASTA）、2（表格）、-1（完整无版本信息） |
| `-o`, `-rasmol`, `-chimerax` | 叠合输出格式 |
| `-m` | 输出旋转矩阵 |
| `-do` | 输出对齐残基对的距离 |

### 比对控制选项

| 选项 | 用途 |
|------|------|
| `-dir`, `-dir1`, `-dir2` | 批量比对：全对全、单侧搜索 |
| `-dirpair` | 按配对列表比对 |
| `-suffix` | 文件名后缀 |
| `-atom` | 代表残基的原子名称：蛋白质默认 " CA "，RNA默认 " C3'" |
| `-fast` | 快速模式（fTM-align 算法） |
| `-TMcut` | TM-score 阈值（预终止） |
| `-het` | 包含 HETATM：0（仅ATOM）、1（ATOM+HETATM）、2（ATOM+MSE） |
| `-mirror` | 镜像结构比对 |
| `-se` | 无叠加的结构比对 |
| `-full` | 显示完整链比对（-mm 2/4） |
| `-closeK` | 序列无关比对的初始近邻数 |
| `-hinge` | 柔性比对的最大铰链数（<10） |
| `-chainmap` | 使用用户提供的链映射文件 |
| `-i`, `-I` | 使用 FASTA 文件中的初始/最终比对 |

### 归一化选项

| 选项 | 用途 |
|------|------|
| `-a` | 按平均长度归一化 |
| `-u`, `-L` | 按指定长度归一化 |
| `-d` | 使用指定 d0 |

## 已知限制和问题

1. **`-mm 1` 与 `-dir` 不兼容**（USalign.cpp:3459）
   - 原因：`-dir` 模式设计用于单体全对全比对，会将 chain1_list 和 chain2_list 设置为相同列表
   - 解决方案：如需寡聚体全对全比对，需手动修改代码实现双重循环

2. **Windows 原生编译不支持压缩文件**
   - Windows 版本无法读取 .gz/.bz2 压缩文件（POSIX 限制）

3. **`-o` 与 `-dir` 的限制**
   - 在 `-dir` 模式下使用 `-o` 或 `-m` 会被禁止，因为输出文件会被不断覆盖

4. **某些选项组合的限制**
   - `-mm` 不能与 `-i`/`-I`、`-u`/`-L`、`-byresi` 一起使用
   - `-mm 1/2` 必须与 `-ter 0/1` 一起使用
   - `-mm 2/4` 不能与 `-dirpair` 一起使用
   - `-chainmap` 必须与 `-mm 1` 一起使用

5. **快速模式的准确性权衡**
   - `-fast` 选项使用 fTM-align 算法，速度更快但准确性略低

## 工作流程

### 基本比对流程
```
解析PDB → 提取坐标和序列 → 二级结构分配 → 多策略初始比对 → 
DP迭代优化 → TM-score计算 → 输出结果
```

### 寡聚体比对流程
```
解析两个复合物 → 全对全链 TM-score 矩阵 → 贪心链分配 → 
质心优化（三聚体+）→ 二聚体调整 → 迭代重比对 → 输出结果
```

## 性能考虑

- 全对全比对复杂度为 O(n²)，其中 n 为列表中文件数量
- 对于较大的列表（>100 个复合物），全对全寡聚体比对可能非常耗时
- 快速模式（`-fast`）可显著提高速度，但会略微降低准确性
- TM-cut 预终止可在比对前过滤不太可能达到阈值的配对，节省时间