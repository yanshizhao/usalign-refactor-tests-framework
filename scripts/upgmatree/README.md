# upgmatree — USalign `-mm 4` (MSTA) 测试数据

## 功能

本目录包含来自 **HOMSTRAD** 数据库 **ABC_tran**（ABC transporter）家族的 6 条蛋白质链，用于测试 **USalign** 的 `-mm 4`（MSTA: Multiple Structure Alignment）多结构比对流程。

### 数据文件

| 文件 | 说明 |
|------|------|
| `1b0ua.atm` ~ `1g6ha.atm` | 6 个单链 PDB 格式结构文件 |
| `list.txt` | 输入列表，每行一个文件名，供 `-dir` 模式使用 |
| `ABC_tran.ali` | HOMSTRAD 多序列比对文件 |
| `ABC_tran.malf` | HOMSTRAD 结构叠加变换文件 |
| `ABC_tran-sup.pdb` | HOMSTRAD 参考叠加结构 |
| `README.md` | 本文件 |

## 编译

### 使用 Makefile

```bash
# 在 USalign 源码目录下执行
cd ../../../USalign

# Linux / macOS
make clean
make

# Windows (MSYS2/MinGW)
mingw32-make clean
mingw32-make
```

`make` 会自动根据平台添加合适的编译选项（Windows 加 `-static`，Linux/macOS 不加）。

### 手动编译

```bash
cd ../../../USalign

# Linux
g++ -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp

# Windows (MSYS2/MinGW)
g++ -static -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp

# macOS（不支持 -static）
g++ -O3 -ffast-math -fopenmp -lm -o USalign USalign.cpp UPGMA.cpp
```

> **说明：**
> - 如需关闭 OpenMP 并行，去掉 `-fopenmp` 即可。
> - 编译出的 `USalign.exe`（Windows）是静态链接的，不依赖 MSYS2 DLL，可拷贝到任何 Windows 机器直接运行。

## 运行

以下命令均假设当前工作目录为 USalign 源码目录（`../../../USalign`）。

### 基本命令

```bash
# 从 USalign 目录执行
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

## 输出结果

运行后会在**当前工作目录**（即 USalign 目录）生成以下文件：

| 文件 | 说明 |
|------|------|
| `upgma_tree.txt` | UPGMA 系统发育树（Newick 格式） |
| `upgma_tree.svg` | UPGMA 树形图（SVG 矢量图） |
| `upgma_tree.dist` | 两两结构之间的 TM-score 距离矩阵 |

终端输出包括：UPGMA 树、多结构比对（FASTA 格式）、统计摘要（平均对齐长度、RMSD、TM-score、序列一致性）。
