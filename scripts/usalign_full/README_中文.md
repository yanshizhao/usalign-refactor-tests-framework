# USalign_full 测试脚本目录

## 📋 脚本运行前的准备工作（必读）

在运行任何测试脚本前，请确保已完成以下步骤：

1. **切换到 master 分支**：
   - 打开终端，进入 `us-align_modify\USalign` 目录
   - 执行 `git checkout master` 切换到 master 分支
   
2. **拉取最新节点**：
   - 执行 `git pull` 获取最新的提交
   - 确保 USalign 源码是最新状态
   
3. **放置源码文件**：
   - 将 `USalign_single_full.cpp` 文件放入 `us-align_modify\USalign` 目录
   - 确保文件路径正确：`us-align_modify\USalign\USalign_single_full.cpp`

4. **返回本目录**：
   - 完成以上步骤后，返回到 `scripts/usalign_full/` 目录
   - 即可开始运行测试脚本

> **注意**：所有测试脚本（`run_full_test.py`、`run_flexalign_test.py`、`run_chainmap_regression.py`）在编译 USalign 时都会自动尝试切换到 master 分支，但建议在运行前先手动完成以上步骤，以确保环境准备就绪。

---

本目录包含 **USalign_full** 相关的自动化测试脚本。这些脚本用于运行功能测试、回归测试，并将当前输出与基线结果进行比较，从而验证代码更改的正确性。

---

## 📁 目录结构

```
scripts/usalign_full/
├── run_full_test.py          # cLanguage2Cplus中用例集testcases_baseline_functional.txt
├── run_flexalign_test.py     # flexalign 中用例集testcases_functional.txt
├── run_chainmap_regression.py # chainmap_local 中用例集testcases_baseline_functional.txt
└── README_中文.md             # 本文件
```

---

## 🚀 快速开始

### 前提条件

1. **USalign 仓库**必须位于 `../../../USalign/`（相对于本脚本目录）
2. **USalign 可执行文件**会自动编译生成：`USalign/USalign_full.exe` 或 `USalign/USalign_full`
3. **测试数据**位于各测试框架的 `data/` 目录中
4. **基线文件**位于各测试框架的 `baseline/` 目录中
5. **Python 3** 环境

---

## 📋 脚本详细说明

### 1. `run_full_test.py` - cLanguage2Cplus中用例集testcases_baseline_functional.txt

**用途**：cLanguage2Cplus中用例集testcases_baseline_functional.txt，使用 **USalign_full.exe** 执行，并与基线结果比较。

**测试数据位置**：
- 测试用例文件：`scripts/cLanguage2Cplus/testcases_baseline_functional.txt`
- 数据目录：`scripts/cLanguage2Cplus/data/`
- 基线目录：`scripts/cLanguage2Cplus/baseline/`
- 当前输出：`scripts/cLanguage2Cplus/current/`
- 差异文件：`scripts/cLanguage2Cplus/diffs/`

**用法**：
```bash
cd scripts/usalign_full
python3 run_full_test.py
```

**测试用例格式**（每行一个测试用例）：
```
test_name workdir_rel pdb1 pdb2 [additional_args...]
```

**功能特性**：
- 自动切换到 USalign 的 `master` 分支编译
- 运行后自动恢复原分支
- 清理上一次测试的输出文件
- 超时设置：60 秒
- 忽略 CPU 时间差异（仅比较实际输出内容）
- 生成统一格式的 diff 文件

---

### 2. `run_flexalign_test.py` - flexalign中用例集testcases_functional.txt

**用途**：flexalign中用例集testcases_functional.txt，使用 **USalign_single_full.cpp** 编译生成的可执行文件。

**测试数据位置**：
- 测试用例文件：`scripts/flexalign/testcases_functional.txt`
- 数据目录：`scripts/flexalign/data/`
- 基线目录：`scripts/flexalign/baseline/`
- 当前输出：`scripts/flexalign/current/`
- 差异文件：`scripts/flexalign/diffs/`

**用法**：
```bash
cd scripts/usalign_full
python3 run_flexalign_test.py
```

**测试用例格式**：
```
test_name workdir_rel pdb_file1 [pdb_file2...] [additional_args...]
```

**功能特性**：
- 自动检查 PDB 文件是否存在
- 如果文件不存在，跳过该测试用例
- 自动清理路径中的冗余 `/` 字符
- 支持 Windows 静态链接编译

---

### 3. `run_chainmap_regression.py` - chainmap_local中用例集testcases_baseline_functional.txt

**用途**：chainmap_local中用例集testcases_baseline_functional.txt，验证代码更改不会破坏现有功能。

**测试数据位置**：
- 测试用例文件：`scripts/chainmap_local/testcases_regression.txt`
- 数据目录：`scripts/chainmap_local/data/`
- 基线目录：`scripts/chainmap_local/baseline/`
- 当前输出：`scripts/chainmap_local/current/`
- 差异文件：`scripts/chainmap_local/diffs/`

**用法**：
```bash
cd scripts/usalign_full
python3 run_chainmap_regression.py
```

**功能特性**：
- 完全清理并重建 `current/` 和 `diffs/` 目录
- 智能检测差异类型：
  - 如果只有 CPU 时间不同，标记为 **WARNING**
  - 如果有实际业务逻辑输出不同，标记为 **FAIL**
- 提供更详细的差异分类

---

## 🔧 通用配置

### 环境变量

所有脚本都支持以下环境变量（可选）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| 无 | - | 目前脚本不使用环境变量配置，所有路径均为硬编码相对路径 |

### 编译选项

所有脚本在编译 USalign 时使用以下选项：
```bash
g++ -O3 -ffast-math -o USalign_full USalign.cpp
```

**Windows 平台**：
```bash
g++ -static -O3 -ffast-math -lm -o USalign_full.exe USalign.cpp
```

---

## 📊 输出格式

### 测试进度显示

```
[1/10] RUN: test_case_name
  CWD: /path/to/data/directory
  CMD: USalign_full pdb1.pdb pdb2.pdb -option value
  [PASS] test_case_name

[2/10] RUN: another_test
  CWD: /path/to/data/directory  
  CMD: USalign_full file1.pdb file2.pdb
  [FAIL] another_test - Output differs from baseline, diff saved to scripts/.../diffs/another_test.diff
```

### 最终汇总

**run_full_test.py 和 run_flexalign_test.py**：
```
============================================================
Results: 45 passed, 2 failed, 1 skipped
============================================================
```

**run_chainmap_regression.py**：
```
============================================================
Results: 45 passed, 1 warning, 2 failed, 1 skipped
============================================================
```

---

## 🎯 测试用例文件格式

### testcases_baseline_functional.txt（run_full_test.py 使用）

```
# 注释行（以 # 开头）
# 格式: test_name workdir_rel pdb1 pdb2 [args...]

# 示例：
test_1h05 1h05 1h05.pdb 1h05.pdb -ter 0
test_1x8a 1x8a 1x8a.pdb 1x8a.pdb -ter 1
```

### testcases_functional.txt（run_flexalign_test.py 使用）

```
# 格式: test_name workdir_rel pdb_file1 [pdb_file2...] [args...]
test_flex_001 chain_001 chainA.pdb chainB.pdb -flex
```

### testcases_regression.txt（run_chainmap_regression.py 使用）

```
# 格式: test_name workdir_rel args...
test_chain_001 dir001 file1.pdb file2.pdb -chain
```

---

## 🔍 差异文件

当测试失败时，脚本会生成差异文件（`.diff`）保存到对应的 `diffs/` 目录中。

差异文件使用 **unified diff** 格式：

```diff
--- baseline/test_name.out
+++ current/test_name.out
@@ -1,5 +1,5 @@
 line1
-line2_old
+line2_new
 line3
```

---

## ⚙️ 自定义测试

### 添加新的测试用例

1. 在对应的 `testcases_*.txt` 文件中添加新行
2. 确保测试数据文件存在于 `data/` 目录中
3. 运行测试生成当前输出
4. 将输出复制到 `baseline/` 目录作为基线

### 创建基线

可以使用 `create_baseline.py` 脚本创建基线文件。例如：

```bash
# 先运行一次测试生成 current/ 输出
python3 run_full_test.py

# 然后复制 current/ 到 baseline/
cp -r scripts/cLanguage2Cplus/current/* scripts/cLanguage2Cplus/baseline/
```

---

## 📝 输出清理规则

所有脚本都会对 USalign 输出进行清理，以确保比较的一致性：

1. **移除冗余的 `/` 字符**：
   ```python
   # 将 "Name of Structure_1: /path/to/file" 中的 / 移除
   re.sub(r'(Name of Structure_\d+:)\s*/', r'\1 ', content)
   
   # 将行首或制表符后的 / 移除（当后面是大写字母时）
   re.sub(r'(^|[\t >])/(?=[A-Z])', r'\1', content, flags=re.MULTILINE)
   ```

2. **忽略 CPU 时间行**：
   ```python
   # 移除所有 "#Total CPU time..." 行
   re.sub(r'^\s*#Total CPU time.*\n?', '', content, flags=re.MULTILINE)
   ```

---

## 🔄 Git 分支处理

所有脚本在编译前都会：

1. 检查 USalign 仓库是否为 Git 仓库
2. 记录当前分支
3. 切换到 `master` 分支进行编译
4. 编译完成后自动切换回原分支

**注意**：如果 USalign 不是 Git 仓库，将直接使用当前状态进行编译。

---

## 📈 返回值

所有脚本的退出码：
- **0**：所有测试通过（`failed == 0`）
- **1**：有测试失败（`failed > 0`）

---

## 📚 相关目录

| 目录 | 用途 |
|------|------|
| `scripts/cLanguage2Cplus/` | 主功能测试框架 |
| `scripts/flexalign/` | FlexAlign 测试框架 |
| `scripts/chainmap_local/` | ChainMap 回归测试框架 |
| `../../../USalign/` | USalign 源码仓库 |

---

## 💡 使用建议

1. **定期更新基线**：当 USalign 代码有重大更改时，重新生成基线文件
2. **检查差异文件**：测试失败时，仔细查看生成的 `.diff` 文件了解具体差异
3. **分批运行**：如果测试用例较多，可以临时修改测试用例文件，只运行部分测试
4. **保存日志**：建议将测试输出重定向到日志文件：`python3 run_full_test.py 2>&1 | tee test_log.txt`

---

## 🔗 快速链接

- [USalign 主仓库](../../../USalign/)
- [测试框架根目录](../../)
- [cLanguage2Cplus 测试框架](../cLanguage2Cplus/)
- [FlexAlign 测试框架](../flexalign/)
- [ChainMap 测试框架](../chainmap_local/)

---

*最后更新：2026-08-24*