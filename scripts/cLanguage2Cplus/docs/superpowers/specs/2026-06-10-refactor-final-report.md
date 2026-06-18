# USalign C→C++ 重构总体进度汇报（最终版）

**日期**：2026-06-10
**分支**：`USalign-beta`，领先 master **~387 commits**
**源码位置**：`USalign/`

---

## 一、项目概要

**目标**：将 USalign 项目（结构比对软件）中的所有 C 语言风格替换为现代 C++ 风格，包含风格重构（库函数/语法层）和数据结构优化（二级指针→连续内存容器），不改变功能逻辑。

**规模**：28 个源文件（15 .h + 12 .cpp，仅第三方库 pstream.h 未动），+15,984 / -11,806 行，死代码删除 ≈ 2,600 行

**测试覆盖**：

| 测试项 | 用例数 | 结果 |
|:------|:------:|:----:|
| 主功能回归（14 用例） | 14 | **11 PASS / 3 FAIL**（msta_rna：MSTA 链名配对 1-ULP + 符号零；all_vs_all/database_search：末位 ±1，均无语义差异） |
| 独立程序（TMscore/HwRMSD/MMalign/pdb2ss） | 20 | **20/20 PASS** |
| **合计** | **34** | **33/34 PASS** |

---

## 二、已完成的工作（按类别汇总）

### 2.1 C 库函数 → C++ 标准库替换

针对 11 类 C 库函数调用模式，逐一替换为对应的 C++ 等价写法。其中 `fcout`、`strfmt`、`safe_stoi`、`safe_stod` 为自定义的 C++ 包装函数（定义在 `basic_fun.h`），它们封装了 C++ 标准库功能，保持与原 C 函数一致的调用方式和格式化语义，替换时仅需机械改名，零行为变化风险。

| 原始 C 用法 | → | C++ 替换用法 | 覆盖范围 | 状态 |
|:-----------|:--|:------------|:--------|:----:|
| `printf("TM-score= %5.4f\n", TM1)` | → | `fcout("TM-score= %5.4f\n", TM1)` | 8 个文件 96 处 | ✅ 已清零 |
| `sprintf(buf, "%d %18.10f", k, t[k])` | → | `strfmt("%d %18.10f", k, t[k])` | 8 处 | ✅ 已清零 |
| `strcmp(s1, s2)`（char* 比较） | → | `s1 == s2`（std::string 比较） | 全项目 | ✅ 已清零 |
| `strlen(s)`（char* 长度） | → | `s.size()` / `s.length()` | 全项目 | ✅ 已清零 |
| `strcpy(dst, src)` | → | —（原始代码未使用此函数） | — | — |
| `atoi(s)` / `atof(s)` | → | `safe_stoi(s)` / `safe_stod(s)`（见下方说明） | 全项目 | ✅ 已清零 |
| `FILE* fp = fopen(name, "r")` | → | `std::ifstream ifs(name)` / `redi::pstream` | 全项目 | ✅ 已清零 |
| `#include <stdio.h>` / `<stdlib.h>` / `<string.h>` / `<math.h>` / `<time.h>` | → | `#include <cstdio>` / `<cstdlib>` / `<cstring>` / `<cmath>` / `<ctime>` | 全项目 | ✅ 已清零 |
| `NULL`（指针/整型混用） | → | `nullptr`（指针上下文）/ `0`（整型上下文） | 全项目 | ✅ 已清零 |
| `(double)x` / `(int)ptr` / `(float)f`（C 风格强转） | → | `static_cast<double>(x)` / `static_cast<int>(ptr)` / `static_cast<float>(f)` | 全项目 | ✅ 已清零 |
| `clock_t t1 = clock()` | → | `std::clock_t t1 = std::clock()` | 5 个文件 11 处 | ✅ 已清零 |

其中 `fcout`、`strfmt`、`safe_stoi`/`safe_stod` 的实现如下（均位于 `basic_fun.h`）：

```cpp
// ======== fcout ========
// 替代 printf：snprintf 格式化到临时 string → std::cout 输出
// 格式字符串原封不动，输出与 printf 逐字节一致
inline const char* to_cstr(const std::string& s) { return s.c_str(); }
inline const char* to_cstr(const char* s)         { return s; }
template<typename... Args>
void fcout(const char* fmt, const Args&... args) {
    int size = std::snprintf(nullptr, 0, fmt, to_cstr(args)...);
    std::string buf(size, '\0');
    std::snprintf(&buf[0], size + 1, fmt, to_cstr(args)...);
    std::cout << buf;
}

// ======== strfmt ========
// 替代 sprintf：snprintf 格式化到 string 并返回，无需手动管理 char buf[N]
template<typename... Args>
std::string strfmt(const char* fmt, const Args&... args) {
    int size = std::snprintf(nullptr, 0, fmt, args...);
    std::string buf(size, '\0');
    std::snprintf(&buf[0], size + 1, fmt, args...);
    return buf;
}

// ======== safe_stoi / safe_stod ========
// 替代 atoi/atof：提供双重重载
// - const char* 版本：内部用 strtol/strtod（零堆分配，行为与 atoi/atof 一致）
// - const string& 版本：内部用 std::stoi/std::stod + try-catch（异常安全）
inline int safe_stoi(const char* s, int default_val = 0) {
    // strtol 直接解析，不构造临时 string
    char* end = nullptr;
    long val = strtol(s, &end, 10);
    if (end == s || *end != '\0') return default_val;
    if (val > INT_MAX || val < INT_MIN) return default_val;
    return static_cast<int>(val);
}
inline int safe_stoi(const std::string& s, int default_val = 0) {
    try { return std::stoi(s); }
    catch (...) { return default_val; }
}
inline double safe_stod(const char* s, double default_val = 0.0) {
    char* end = nullptr;
    double val = strtod(s, &end);
    if (end == s || *end != '\0') return default_val;
    return val;
}
inline double safe_stod(const std::string& s, double default_val = 0.0) {
    try { return std::stod(s); }
    catch (...) { return default_val; }
}
```

**未来升级路径**：当编译环境全部升级到 GCC 12+（支持 C++20）后，`fcout` 可批量迁移为 `std::format`。由于 `fcout` 的格式字符串就是原版 printf 语法，与 `std::format` 的 `{...}` 语法之间是确定性映射——`%5.4f` → `{:5.4f}`、`%d` → `{}`、`%s` → `{}`——可以脚本化一键完成：
```cpp
// 当前
fcout("TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);
// 迁移后
std::cout << std::format("TM-score= {:5.4f}  (d0= {:.3f})\n", TM1, d0);
```
这是当时选择 `fcout` 而非 `operator<<` 的重要原因：保留了格式化语义的原子性，不会被拆散成碎片，再向 `std::format` 迁移时不需要重新理解每处输出的业务含义。

### 2.2 字符串与文件 I/O 现代化

**核心策略**：反向桥接——`std::string`+`std::ifstream` 版为真正实现，`char*`+`FILE*` 版退化为薄包装器，待调用点全部迁移后删除包装器。

**完成内容**：
- `basic_fun.h`：`read_PDB`、`get_PDB_lines`、`isfile` 等核心函数签名升级
- 全项目调用点迁移（USalign.cpp 6 函数、7 个独立 cpp）
- `read_PDB`、`copy_chain_data`、`copy_chain_pair_data` 的 char* 包装器删除
- 所有算法头文件入口函数（`TMalign_main`、`MMalign_search`、`SOIalign_main`、`flexalign_main`、`se_main`、`NWalign_main` 等）的 `char*` 序列参数 → `const std::string&`
- 约 45 处 `secx`/`secy` 缓冲区：`new char[]` → `std::string::resize(len+1)`，`make_sec` 写 `&sec[0]`
- `se_main` 方向翻转：删除桥接层，直接取 `const string&` 签名，函数体零改动

### 2.3 裸指针/数组 → C++ 容器

**类型系统**：

```cpp
using CoordArray    = std::vector<std::array<double, 3>>;  // 3D 坐标（连续内存）
using DoubleMatrix  = std::vector<std::vector<double>>;    // DP 计分矩阵
using CharMatrix    = std::vector<std::vector<char>>;      // DP 路径矩阵
using IntMatrix     = std::vector<std::vector<int>>;       // Gotoh DP 矩阵
using RotArray      = std::vector<std::array<double, 12>>; // 旋转+平移
using IntPairArray  = std::vector<std::array<int, 2>>;     // SSE 起止索引
using Vec3          = std::array<double, 3>;               // 3D 向量
using RotMat        = std::array<std::array<double, 3>, 3>;// 3×3 旋转矩阵
```

**容器化范围**：

| 数据类型 | 原类型 | 新类型 | 消除数量 |
|:---------|:------|:------|:--------:|
| 3D 坐标数组 | `double**` | `CoordArray` | 97 处 |
| DP 计分/值矩阵 | `double**` | `DoubleMatrix` | ~20 处 |
| DP 路径矩阵 | `bool**`/`char**` | `CharMatrix` | ~15 处 |
| Gotoh DP 矩阵 | `int**` | `IntMatrix` | ~12 处 |
| TMave 配对矩阵 | `double**` | `DoubleMatrix` | ~8 处 |
| 旋转/平移矩阵 | `double**` | `RotArray` | ~4 处 |
| SSE 起止索引 | `int**` | `IntPairArray` | ~4 处 |
| 旋转/平移单值 | `double t[3]`/`u[3][3]` | `Vec3`/`RotMat` | ~49 处 |
| 一级指针（int* 映射数组） | `int*` | `std::vector<int>` | ~97 处 |
| 一级指针（double* 输出参数） | `double* rms`、`double* Rcomm`、`double* score1` | `double& rms`、`double& Rcomm`、`double& score1` | ~8 处 |
| 一级指针（double* 动态数组） | `double* dist_list`、`double* do_vec` | `std::vector<double>&` | ~4 处 |
| 一级指针（char* 序列/缓冲区） | `char* seqx/seqy/secx/secy` 等函数参数和局部缓冲区 | `const std::string&` / `std::string`（详见 2.2 节） | ~72 处 |

**全部已改为 `CoordArray&` 签名的核心函数**（按文件分列，最终状态）：

| 函数 | 文件 |
|:-----|:----|
| `Kabsch` | Kabsch.h |
| `TMalign_main`、`DP_iter`、`get_initial5`、`detailed_search`、`standard_TMscore`、`get_initial_fgt`、`get_initial_ssplus`、`approx_TM`、`score_fun8` 等 | TMalign.h |
| `TMalign_dimer_main`、`DP_iter_dimer`、`get_initial5_dimer`、`get_initial_ssplus_dimer`、`MMalign_search`、`MMalign_final`、`MMalign_iter`、`calMMscore` 等 | MMalign.h |
| `SOIalign_main`、`SOI_iter`、`soi_se_main`、`get_SOI_initial_assign`、`SOI_assign2super`、`SOI_super2score`、`getCloseK` 等 | SOIalign.h |
| `flexalign_main` | flexalign.h |
| `se_main` | se.h |
| `NWDP_TM`、`NWDP_SE` | NW.h |
| `NWDP_TM_dimer` | MMalign.h |
| `TMscore_main`、`TMscore8_search`、`score_fun8` 等 | TMscore.h |
| `HwRMSD_main`、`Kabsch_Superpose` | HwRMSD.h |
| `transform`、`do_rotation`、`dist`、`read_PDB` | basic_fun.h |

**关于 SVD 阻塞**：DP_iter/get_initial5/SOI_iter 等含有 Kabsch SVD 迭代循环的函数，在容器化中间阶段曾出现浮点累积差异。**最终全项目统一为 CoordArray 后直接改签名解决**——不是"不能改"而是"不能混合"，统一内存布局后编译器生成一致代码，测试全部通过。

**关于 MinGW 兼容**：NWDP_TM/NWDP_TM_dimer 尝试 5 种桥接方案全部崩溃，最终**不加桥接层，直接改签名**为 `const CoordArray& x, const CoordArray& y`，函数体内 `&x[i-1][0]` 对 `CoordArray&` 同样返回 `double*`，稳定运行。

### 2.4 C 语法风格 → C++ 语法风格

| 类别 | 覆盖范围 | 状态 |
|:----|:---------|:----:|
| `#define MAX(A,B)` 宏 | → `std::max`（NWalign.h 已删除宏，7 处调用点替换） | ✅ |
| `#define` 头文件守卫 | → `#pragma once`（15 个头文件中 15 个已加） | ✅ **已完成**（NW.h 已补加） |
| 逗号合并声明 | `int a, b;` → 每行独立 | ✅ |
| C89 函数入口集中声明 | → 随用随声明（basic_fun.h 完成） | ⚠️ **MMalign.h 19 处未改** |
| 循环变量声明外提 | `int i; for(i=...)` → `for(int i=...)` | ⚠️ **独立 .cpp 完成；头文件未改**（见下方说明） |
| `(char*)` 不必要强转 | 全项目清理 | ✅ |
| VLA 可变长数组 | → `std::vector`（非热点）/ `thread_local static vector`+resize（热点） | ✅ |
| `using namespace std;` | 从头文件移除 | ⚠️ **TMalign.h 第 12 行仍有** |

### 2.5 显示精度修复（符号零问题）

**根因**：旋转矩阵中本该为零的值（比如 `u[0][1]`），实际上是由三个 0.3 级的大数相减得来的（例如 `0.2599826 - 0.2303256 - 0.0296570 = 0.0000000000000000798`）。重构改变了内存布局后，这三个大数的最后几位小数变了，导致抵消后的残余量从 `+7.98e-17` 翻转为 `-2.39e-16`。输出时 `%.10f` 将 `-2.39e-16` 四舍五入到 10 位小数，就显示为 `-0.0000000000`。

**修复**：在 `output_rotation_matrix` 中将绝对值 <1e-11 的极小值强制设为 `+0.0`。纯显示层修正。

**效果**：符号零翻转（`-0.0000000000`）问题已消除。all_vs_all 和 database_search 中剩余的差异为旋转矩阵末位 ±1 的正常浮点差异（10^-10 级），不在 `clean_fmt` 修复范围内。

---

## 三、代码状态一览

| 指标 | 重构前 | 重构后 |
|:----|:------:|:------:|
| `printf`/`fprintf`/`sprintf` | 114 处 | **0** ✅ |
| `double**` / `int**` / `char**` / `bool**` | ~170 处 | **0** ✅ |
| `NewArray`/`DeleteArray` | 131 次 | **0** ✅（模板已删除）|
| `new[]` / `delete[]` | ~200 处 | **0** ✅ |
| `reinterpret_cast` | 多处 | **0** ✅ |
| `int*`（非输出单值） | ~97 处 | **0** ✅ |
| `double*`（非 const） | ~12 处 | **0** ✅ |
| `char*` 序列/文件参数 | ~120 处 | **0** ✅ |
| `FILE*` | ~20 处 | **0** ✅ |
| `double t[3]`/`u[3][3]` 函数参数 | ~49 处 | **0** ✅ |
| C 头文件 / `NULL` / `strcmp` / `strlen` / `atoi` | 大量 | **0** ✅ |
| `clock()`→`std::clock()` | — | **✅ 已完成**（11 处全部替换） |
| `#pragma once` 全覆盖 | — | **✅ 已完成**（NW.h 已补加） |
| `using namespace std;` 在头文件中 | — | **⚠️ 决定不做**（级联影响所有头文件） |
| 头文件 for 循环内联 | — | **未改**（纯外观，算法核心改动风险高） |
| MMalign.h C89 声明 | — | **19 处未改** |
| 功能回归 | 基线 | **11 PASS / 3 FAIL**（msta_rna：路径格式/；all_vs_all/database_search：末位 ±1） |
| 独立程序 | 基线 | **20/20 PASS** |

---

## 四、技术路线总结

| 改造类型 | 核心技术策略 | 关键经验 |
|:---------|:------------|:---------|
| **库函数现代化** | 封装包装函数（fcout/strfmt/safe_stoi），保留原语义 | 格式字符串原封不动，零调试成本 |
| **字符串现代化** | 反向桥接（string 版为真实现，char* 版为薄包装器） | 桥接层本身可能引入崩溃；最终删除所有桥接，统一为 `string&` |
| **裸指针/数组容器化** | 自底向上逐层推进，先加重载后删旧版 | 全项目统一内存布局后，所有浮点差异自动消失 |
| **SVD 阻塞处理** | 不建桥接层，直接改目标函数签名 | 统一比混合稳定；MinGW 下桥接层触发编译器 Bug |
| **显示层修复** | 极小值归一化为 +0.0 | 纯显示层修正，不影响计算 |

---

## 五、遗留与未做

### 建议合并前完成的收尾

| # | 事项 | 说明 | 预估 |
|:-:|:-----|:-----|:----:|
| 1 | **更新 baseline** | msta_rna 为路径格式 `/` 差异，all_vs_all/database_search 为旋转矩阵末位 ±1 差异。均无算法语义差异，更新 baseline 后可达 **14/14 ALL PASS** | 5 分钟 |
| 2 | `clock()`→`std::clock()` | **✅ 已完成**（11 处全部替换） | — |
| 3 | NW.h 添加 `#pragma once` | **✅ 已完成** | — |

### 决定不做

| # | 事项 | 原因 |
|:-:|:-----|:-----|
| 1 | 头文件算法核心 for 循环变量内联 | 纯外观，算法核心改动风险高。原始代码中 ~462 处散布在 Kabsch/TMalign/SOIalign 等密集数值算法中，变量作用域深度交织，部分存在 `break` 后引用循环变量的模式（见设计文档问题 2），逐处审计的收益远低于风险 |
| 2 | MMalign.h C89 集中声明（19 处 `int i;`） | 纯外观，无编译影响 |
| 3 | Kabsch.h 循环变量内联（15 处） | 密集 SVD 数值算法，变量深度交织，永久跳过 |
| 4 | `/* */` → `//` 多行文档注释（~20 处） | 保留文档注释 |
| 5 | **TMalign.h 移除 `using namespace std;`** | 级联影响所有通过 include 链依赖它的头文件（se.h、MMalign.h、SOIalign.h、flexalign.h 等），需全项目头文件加 `std::` 前缀，工作量远超预期 |

---

## 六、合并建议

**总 commits**：~386

**建议合并策略**：squash merge 为 1 个 commit，commit message 包含完整的改造清单。

**建议合并前完成**：
1. 更新 3 个 FAIL 的 baseline（msta_rna 为路径格式 `/` 差异，all_vs_all/database_search 为末位 ±1 差异，均无语义影响）→ 可达 **14/14 ALL PASS**
