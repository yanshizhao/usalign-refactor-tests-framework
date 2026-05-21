# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目目的

**USalign** 的回归与性能测试框架。USalign 是一款通用的蛋白质/核酸结构比对工具（张阳实验室，版本 20260329，发表于 Nature Protocols 2026 和 Nature Methods 2022）。该框架用于验证对 `../../../USalign/USalign.cpp` 的修改不会引入功能回归或性能退化。

## 常用命令

所有脚本必须在 `cLanguage2Cplus/` 目录下运行：

```bash
cd cLanguage2Cplus

# 编译原始版 USalign 并创建功能基线
python create_baseline.py

# 编译修改版 USalign 并运行功能回归测试
python run_regression.py

# 编译原始版 USalign 并创建性能基线
python create_perf_baseline.py

# 编译修改版 USalign 并运行性能回归测试
python run_perf_test.py

# 构建 smallDB 测试数据库（需要 data/PDB/PDB/ 下有 PDB 文件）
python build_Small_DB.py
```

每个脚本在运行前会自动编译对应的 USalign 源码。原始版和修改版可执行文件分别生成为当前目录下的 `USalign_orig.exe` 和 `USalign_mod.exe`。

手动编译 USalign：
```bash
g++ -O3 -ffast-math -lm -o USalign.exe ../../../USalign/USalign.cpp
```

## 架构

### 双可执行文件比对模式

该框架通过比对两个独立编译的可执行文件来工作——**原始版**（`USalign_orig.exe`，由未修改源码编译）和**修改版**（`USalign_mod.exe`，由当前编辑的源码编译）。两者都从同一个 `../../../USalign/USalign.cpp` 文件编译，工作流如下：

1. **修改源码前**：运行 `create_baseline.py` 和 `create_perf_baseline.py`，从未修改的代码中捕获黄金标准输出和基线耗时。
2. **编辑 `../../../USalign/USalign.cpp`**。
3. **修改源码后**：运行 `run_regression.py` 和 `run_perf_test.py`，验证输出一致性且性能未退化。

首次克隆时，`USalign_orig.exe` 和 `USalign_mod.exe` 可能已作为预编译二进制文件存在于工作目录中。`baseline/` 中的基线输出文件是由原始版本生成的。

### 测试用例格式

测试用例定义在两个纯文本文件中，每行一个：

```
<名称> <工作目录> <参数...>
```

- `testcases_functional.txt` — 14 个功能测试用例
- `testcases_performance.txt` — 4 个性能测试用例
- 以 `#` 开头的行是注释
- `<工作目录>` 相对于 `data/`（用 `.` 表示 data 根目录）
- 脚本启动 USalign 前，会先将 `cwd` 设为指定的 data 子目录

### 输出比对逻辑

`run_regression.py` 对基线输出和当前输出进行**逐字节比对**（对原始字节使用 `==`）。比对前会先调用 `clean_slash()` 函数，去除 `Name of Structure_X:` 行中多余的 `/` 前缀——这是 USalign 输出中的一个已知瑕疵，通过清洗来消除干扰。

当输出不一致时，会在 `diffs/<用例名>.diff` 中生成 unified diff。`superposed_structure` 用例还会额外比对生成的 `sup.pdb` 结构文件。

### 性能阈值

`run_perf_test.py` 中的性能回归阈值：
- `<20%` 变化 → PASS（通过）
- `20%-50%` 变化 → WARNING（警告，需关注）
- `>50%` 变化 → FAIL（失败，性能显著退化）

每个性能测试运行 5 次，取 USalign 输出中 `#Total CPU time` 的平均值。

### USalign 源码结构

`../../../USalign/USalign.cpp`（约 3200 行）是主入口——解析命令行参数后委托给以下头文件模板库：

- `MMalign.h` — 寡聚体/复合物多链比对（-mm 模式）
- `SOIalign.h` — 序列顺序无关比对
- `flexalign.h` — 柔性铰链比对
- `TMalign.h` — 核心 TM-align 算法（双结构比对）
- `TMscore.h` — 无需重新比对的 TM-score 计算（-TMscore）
- `Kabsch.h` — 最优叠合（Kabsch 算法）
- `NW.h` / `NWalign.h` — Needleman-Wunsch 序列比对
- `se.h` — 二级结构分配

### 数据目录布局

- `data/*.pdb`、`data/*.pdb1` — 单结构测试输入
- `data/help/` — 比对引导的 TM-score 测试输入（model/native 配对）
- `data/MSTATest/` — RNA 多结构比对测试集，含 `list.txt`
- `data/PDB/PDB/` — 大量 PDB 文件集合，供 `build_Small_DB.py` 使用
- `data/smallDB/` — 随机抽取的 100 个结构子集，用于数据库搜索测试

## 重要约定

- `baseline/` 和 `current/` 中的输出文件以 `<测试名>.out` 命名。修改版会在文件名中追加 `_mod` 后缀（如 `standard_protein_mod.out`）。
- 测试用例中的 `-outfmt -1` 选项用于输出版本和引用信息，使输出具有确定性，便于比对。
- `-m -` 选项将旋转矩阵输出到 stdout（被基线捕获）。
- `-dir` 和 `-dir2` 参数在 Windows 下使用反斜杠路径分隔符（`.\`）。
- `superposed_structure` 是特殊用例：它生成 `sup.pdb` 文件，需要单独移动和比对；生成的 `.pml` 文件会被清理删除。
- 每次运行时，测试脚本会自动清空并重建 `current/`、`diffs/`、`perf_current/` 目录。切勿在这些目录中存放重要文件。
- `USalign_orig.exe` 和 `USalign_mod.exe` 文件大小可能相同，但 md5 不同——说明源码已被修改并重新编译。
