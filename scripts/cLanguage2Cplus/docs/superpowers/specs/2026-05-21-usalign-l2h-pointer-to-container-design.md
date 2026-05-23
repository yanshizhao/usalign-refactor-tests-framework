# L2-h: 二级指针 → C++ 容器 详细改造方案

## 1. 现状分析

### 1.1 数据总览

| 指标 | 数值 |
|------|------|
| `NewArray` 总调用点 | 131 |
| 坐标数组（dim2=3） | 97（74%） |
| 非坐标数组（dim2≠3） | 34（26%） |
| 涉及文件 | 17（10 .h + 7 .cpp） |
| 模板类型 | `double`、`int`、`bool` |
| 内存分配方式 | `NewArray`（逐行独立 `new[]`，碎片化堆分配） |

### 1.2 当前内存布局问题

```
double **xa
  ┌───┬───┬───┬───┬───┐        每行独立 new[]
  │ · │ · │ · │ · │ · │ ──→ [x₀ y₀ z₀] [x₁ y₁ z₁] [x₂ y₂ z₂] ...
  └───┴───┴───┴───┴───┘    （各行在堆中不连续，cache miss 高）
```

核心算法（Kabsch、score_fun8、NWDP_TM）在数百万次级循环中逐行读取坐标，当前碎片化布局导致大量 cache miss。

### 1.3 分类体系

| 类别 | 类型 | dim2 | 数量 | 新类型 |
|------|------|------|------|--------|
| **A: 3D 坐标** | `double**` | 3 | 97 处 | `vector<array<double,3>>` |
| **B: DP 计分矩阵** | `double**` | `ylen+1` | 12 处 | `vector<vector<double>>` |
| **C: DP 路径矩阵** | `bool**` | `ylen+1` | 10 处 | `vector<vector<char>>` |
| **D: Gotoh DP** | `int**` | `ylen+1` | 12 处 | `vector<vector<int>>` |
| **E: TMave 矩阵** | `double**` | `chain2_num` | 6 处 | `vector<vector<double>>` |
| **F: 旋转/平移** | `double**` | 12 | 4 处 | `vector<array<double,12>>` |
| **G: SSE 边界** | `int**` | 2 | 2 处 | `vector<array<int,2>>` |

## 2. 核心设计

### 2.1 类型定义

```cpp
// basic_fun.h 新增类型别名
#include <vector>
#include <array>

using Coords    = std::vector<std::array<double, 3>>;  // 3D 坐标
using DPMatrix  = std::vector<std::vector<double>>;     // DP 计分/值矩阵
using PathMat   = std::vector<std::vector<char>>;       // DP 路径矩阵（不用 vector<bool>）
using IntMat    = std::vector<std::vector<int>>;         // Gotoh DP 矩阵
using Rotation  = std::vector<std::array<double, 12>>;   // 旋转+平移 (3×3 + 3)
using Bond2     = std::vector<std::array<int, 2>>;       // SSE 起止索引
```

### 2.2 关键语法等价性

`xa[i][j]` 在 `double**` 和 `Coords&` 下语义完全相同，这是本方案的前提：

```cpp
// 旧代码
double **xa;
NewArray(&xa, n, 3);
xa[i][0] = x;  // OK
TMalign_main(xa, ya, ...);  // 传递
DeleteArray(&xa, n);

// 新代码
Coords xa(n);        // 一行替代 NewArray
xa[i][0] = x;        // 完全相同
TMalign_main(xa, ya, ...);  // 传递（签名改为 Coords&）
// 自动析构，替代 DeleteArray
```

### 2.3 函数签名转换对照

| 旧参数 | 新参数 | 索引语法 |
|--------|--------|---------|
| `double **xa`（坐标） | `Coords& xa` | `xa[i][j]` 不变 |
| `double **score`（DP） | `DPMatrix& score` | `score[i][j]` 不变 |
| `bool **path`（DP） | `PathMat& path` | `path[i][j]` 不变（值从 `true/false` 变为 `1/0`） |
| `int **S`（Gotoh） | `IntMat& S` | `S[i][j]` 不变 |
| `double **TMave_mat` | `DPMatrix& TMave_mat` | `TMave_mat[i][j]` 不变 |
| `double **ut_mat`（旋转） | `Rotation& ut_mat` | `ut_mat[i][j]` 不变 |
| `int **secx_bond`（SSE） | `Bond2& secx_bond` | `secx_bond[i][j]` 不变 |

### 2.4 为什么不使用模板化函数签名

Naïve 方案：
```cpp
template<typename T>
int TMalign_main(T& xa, T& ya, ...);
```

**不可行原因**：
- `TMalign_main` 约 500 行，`MMalign_search` 约 300 行——这些巨型函数作为模板会爆炸式增加编译时间
- 模板实例化放在头文件中会导致多个编译单元各自实例化，链接冲突
- `double**` 和 `Coords&` 虽然 `[i][j]` 语法相同，但其他操作（如 `xa = nullptr`、`DeleteArray`）差异巨大，模板实例化后会暴露这些差异

## 3. 执行策略：反向桥接 + 逐文件推进

### 3.1 核心策略

采用与 char* → string 里程碑相同的**反向桥接**策略，但简化版：

1. **深层函数**（被多处调用）→ 新增 `Coords&` 重载 + 旧 `double**` 版退化为包装器
2. **中层/顶层函数** → 直接改签名（调用者数量可控）
3. **调用点** → 逐文件迁移
4. **旧包装器** → 确认零调用后删除

### 3.2 为什么用反向桥接

以 `Kabsch` 为例——它是被数十个函数调用的核心算法：

- `Kabsch(double **x, double **y, ...)` → 改为包装器
- 新增 `Kabsch(Coords& x, Coords& y, ...)` → 真正实现
- 包装器内部：从 `double**` 创建临时 `Coords` 视图 → 调用新重载 → 拷回结果

这种做法的优势：**M-1 步只改 Kabsch 一个函数，零调用点修改，零编译风险**。

### 3.3 指针视图桥接

`double**` 包装器内部需要将数据桥接到 `Coords&`：

```cpp
// 包装器（无拷贝开销——直接引用原数据）
bool Kabsch(double **x, double **y, int n, int mode, double *rms,
            double t[3], double u[3][3])
{
    // 注意：Coords 不能直接从 double** 零拷贝构造
    // 但 Kabsch 是只读的（不修改 x, y 内容），所以这里用 const 视图
    // 方案：在包装器中用循环拷贝？不——会影响性能。
    // 
    // 实际方案：Kabsch 内部只通过 x[i][j] 访问，不分配/释放内存
    // 因此我们不需要桥接——直接让 Kabsch 同时支持 Coords& 和 double**
    // 通过函数重载。
}
```

**关于只读函数的特例**：`Kabsch` 只读取 `x` 和 `y`，不修改。对于这类只读函数，两个重载可以共享同一个实现——因为只读操作在 `double**` 和 `Coords&` 上完全等价。

但 C++ 中，不能直接将 `double**` 传给 `const Coords&` 参数。因此需要桥接。由于 Kabsch 在热点循环中被调用数百万次，不能有额外开销。

**最终决定**：对热点只读函数（Kabsch、score_fun8、make_sec、approx_TM），**先新增 Coords& 重载（真实现），原 double** 版保留原实现**（不删除），等所有调用者迁移完毕后再删除旧版。

对非热点函数和读写函数，使用以下桥接模式：

```cpp
// 为 double** 到 Coords& 的零拷贝桥接
// 创建一个轻量视图包装器
struct CoordView {
    double* const* ptrs;  // 指向原始 double** 的行指针数组
    int n;
    
    double* operator[](int i) { return ptrs[i]; }
    const double* operator[](int i) const { return ptrs[i]; }
};
```

但在本方案中，为减少新增基础设施的复杂度，统一采用**重载策略**——在旧 `double**` 函数体旁边新增 `Coords&` 版，作为真正的实现。两个重载各自独立编译，等迁移完成后删除旧版。

## 4. 改造顺序（自底向上）

### 基本原则
- 先改被依赖的底层函数，再改依赖它们的高层函数
- 同一文件内的函数尽量一批处理
- 每步 1-2 个文件，编译 → 测试 → commit

### 4.1 阶段 0：基础设施（basic_fun.h）

| 步骤 | 内容 | 风险 |
|------|------|------|
| **L2h-0a** | 在 `basic_fun.h` 中定义类型别名（Coords, DPMatrix, PathMat, IntMat, Rotation, Bond2） | 零（仅新增代码） |
| **L2h-0b** | `read_PDB`（basic_fun.h:798）新增 `Coords&` 重载；旧 `double**` 版改为包装器 | 低 |
| **L2h-0c** | `do_rotation`（basic_fun.h:839）同上 | 低 |

### 4.2 阶段 1：核心算法底层（只读函数优先）

| 步骤 | 文件 | 函数 | 风险 |
|------|------|------|------|
| **L2h-1a** | Kabsch.h | `Kabsch` — 只读，新增 `Coords&` 重载 | **高**（热点，需性能验证） |
| **L2h-1b** | TMalign.h | `score_fun8` + `score_fun8_standard` — 只读 | 中（热点） |
| **L2h-1c** | TMalign.h | `make_sec`（2 个重载）— 只读 x | 低 |
| **L2h-1d** | TMalign.h | `find_max_frag`、`approx_TM`、`get_score_fast` — 只读 | 低 |

### 4.3 阶段 2：算法读写函数

| 步骤 | 文件 | 函数 | 风险 |
|------|------|------|------|
| **L2h-2a** | TMalign.h | `get_initial`、`get_initial5`、`get_initial_fgt` | 中 |
| **L2h-2b** | TMalign.h | `DP_iter`、`standard_TMscore`、`detailed_search` | 中 |
| **L2h-2c** | TMalign.h | `TMscore8_search`、`get_initial_ss`、`get_initial_ssplus`、`score_matrix_rmsd_sec` | 中 |
| **L2h-2d** | NW.h | `NWDP_TM`（3 重载）、`NWDP_SE`（2 重载）— DP 核心 | 中 |
| **L2h-2e** | se.h | `se_main`（2 重载）— DP score/val | 中 |
| **L2h-2f** | TMscore.h | 与 TMalign.h 同名的函数（独立程序副本） | 中 |

### 4.4 阶段 3：中层算法函数

| 步骤 | 文件 | 函数 | 风险 |
|------|------|------|------|
| **L2h-3a** | TMalign.h | `TMalign_main`、`CPalign_main`、`clean_up_after_approx_TM` | **高**（入口函数） |
| **L2h-3b** | HwRMSD.h | `HwRMSD_main`、`Kabsch_Superpose` | 中（独立程序） |
| **L2h-3c** | SOIalign.h | `SOIalign_main`、`SOI_iter`、`getCloseK` 等全部 ~8 函数 | 中 |
| **L2h-3d** | flexalign.h | `flexalign_main` | 低 |
| **L2h-3e** | MMalign.h | `TMalign_dimer_main`、`MMalign_search`、`MMalign_final`、`MMalign_dimer`、`MMalign_iter` 等全部 ~20 函数 | **高**（函数多，调用链深） |
| **L2h-3f** | NWalign.h | `NWalign_main`、`calculate_score_gotoh`、`trace_back_gotoh`、`trace_back_sw` | 中（int**） |

### 4.5 阶段 4：入口 .cpp 文件

| 步骤 | 文件 | 改动 | 风险 |
|------|------|------|------|
| **L2h-4a** | TMalign.cpp | 分配点：`NewArray(&xa, xlen, 3)` → `Coords xa(xlen)` | 低 |
| **L2h-4b** | TMscore.cpp | 同上 | 低 |
| **L2h-4c** | HwRMSD.cpp | 同上 | 低 |
| **L2h-4d** | MMalign.cpp | 同上 + TMave_mat/ut_mat/centroids | 中 |
| **L2h-4e** | se.cpp | 同上 | 低 |
| **L2h-4f** | NWalign.cpp | int** → IntMat | 低 |
| **L2h-4g** | pdb2ss.cpp | xa → Coords | 低 |
| **L2h-4h** | qTMclust.cpp | xa/ya → Coords | 低 |
| **L2h-4i** | biounitasym.cpp | xa/ya → Coords | 低 |
| **L2h-4j** | xyz_sfetch.cpp | 如有 | 低 |

### 4.6 阶段 5：主程序 USalign.cpp

| 步骤 | 内容 | 风险 |
|------|------|------|
| **L2h-5a** | `TMalign()` 函数：xa/ya → Coords | 低 |
| **L2h-5b** | `MMalign()` 函数：xa/ya/TMave_mat/ut_mat/centroids → 新类型 | **高**（最大的函数，分配点多） |
| **L2h-5c** | `USalign()`、`mTMalign()`、`SOIalign()`、`MMdock()` → 同上 | 中 |
| **L2h-5d** | `main()` 函数中的 `TMalign`/`search_databases` 路径 | 中 |

### 4.7 阶段 6：清理

| 步骤 | 内容 |
|------|------|
| **L2h-6a** | 删除 `basic_fun.h` 中 `read_PDB`、`do_rotation` 的旧 `double**` 重载 |
| **L2h-6b** | 删除所有旧的 `double**` 包装器（确认零调用者） |
| **L2h-6c** | 删除 `NewArray` / `DeleteArray` 模板函数（确认零调用者） |

## 5. 类型转换对照表

### 5.1 声明和分配

| 旧代码 | 新代码 |
|--------|--------|
| `double **xa;` | `Coords xa;` |
| `NewArray(&xa, n, 3);` | `xa.resize(n);` |
| `double **score;` | `DPMatrix score;` |
| `NewArray(&score, n+1, m+1);` | `score.assign(n+1, vector<double>(m+1));` |
| `bool **path;` | `PathMat path;` |
| `NewArray(&path, n+1, m+1);` | `path.assign(n+1, vector<char>(m+1));` |
| `int **S;` | `IntMat S;` |
| `NewArray(&S, n+1, m+1);` | `S.assign(n+1, vector<int>(m+1));` |
| `double **TMave_mat;` | `DPMatrix TMave_mat;` |
| `NewArray(&TMave_mat, c1, c2);` | `TMave_mat.assign(c1, vector<double>(c2));` |
| `int **secx_bond;` | `Bond2 secx_bond;` |
| `NewArray(&secx_bond, n, 2);` | `secx_bond.resize(n);` |

### 5.2 清理

| 旧代码 | 新代码 |
|--------|--------|
| `DeleteArray(&xa, n);` | （删除——析构函数自动清理） |
| `DeleteArray(&score, n+1);` | （删除） |
| `DeleteArray(&path, n+1);` | （删除） |

### 5.3 传递到函数

| 旧代码 | 新代码 |
|--------|--------|
| `TMalign_main(xa, ya, ...)` | `TMalign_main(xa, ya, ...)`（签名变为 `Coords&`） |
| `Kabsch(r1, r2, ...)` | `Kabsch(r1, r2, ...)`（同上） |

### 5.4 索引和赋值

| 操作 | 新旧完全一致 |
|------|------------|
| `xa[i][j]` | ✅ |
| `xa[i][0] = 1.0;` | ✅ |
| `score[i][j] = val;` | ✅ |
| `path[i][j] = true;` | ⚠️ 需要改为 `path[i][j] = 1;`（PathMat 是 `vector<vector<char>>`） |
| `S[i][j] = 42;` | ✅ |

### 5.5 空指针检查

| 旧代码 | 新代码 |
|--------|--------|
| `if (xa == nullptr) ...` | `if (xa.empty()) ...` 或直接去掉（vector 默认非空） |
| `if (!xa) ...` | `if (xa.empty()) ...` |
| `xa = nullptr;`（重置） | `xa.clear();` |

## 6. 风险控制

### 6.1 性能风险：热点函数

| 函数 | 调用频率 | 影响 |
|------|---------|------|
| `Kabsch` | 数百万次/测试 | **极高**——必须保持性能 |
| `score_fun8` | 数百万次 | 极高 |
| `NWDP_TM` / `NWDP_SE` | 数十万次 | 高 |
| `do_rotation` | 数十万次 | 高 |
| `DP_iter` | 数千次 | 中 |

**缓解措施**：
- 热点函数优先采用**重载策略**——让编译器为 `Coords&` 和 `double**` 各自生成优化代码
- `Coords`（`vector<array<double,3>>`）的数据是**连续的**，cache 性能理论上优于碎片化 `double**`
- 每完成一个热点函数改造后**立即运行性能测试**（`run_perf_test.py`），确认无性能退化

### 6.2 编译风险：级联签名变更

- `basic_fun.h` 的 `read_PDB` 和 `do_rotation` 被全项目所有文件 include
- 修改它们的签名 → 所有调用点级联编译失败

**缓解措施**：
- 在 L2h-0b/L2h-0c 中，**先新增 Coords& 重载**，**不删除**旧的 `double**` 重载
- 等所有调用点迁移到新重载后（阶段 5 之后），再删除旧重载（阶段 6）

### 6.3 正确性风险：读写语义

- `read_PDB` 内部**写入** `a[i][0..2]`——写入 `Coords` 的 `array<double,3>` 元素，语义等价
- `do_rotation` 内部**读取** `x[i][0..2]`，**写入** `x1[i][0..2]`——读写 `Coords` 语义等价
- Kabsch、score_fun8 等**只读**函数——直接重载，零语义差异

**关键验证**：每步后运行 `run_regression.py`（14 功能测试），必须全部 PASS。

### 6.4 `vector<bool>` 陷阱

**绝对不使用 `vector<vector<bool>>`**。`vector<bool>` 是 C++ 标准库的特化——它不是一个真正的 bool 容器，而是位压缩存储，不支持 `path[i][j]` 作为左值引用。

使用 **`vector<vector<char>>`**（PathMat 类型别名）替代：
- `path[i][j] = true` → `path[i][j] = 1`
- `path[i][j] = false` → `path[i][j] = 0`
- `if (path[i][j])` → ✅ 完全等价（隐式转换为 bool）

## 7. 验证策略

### 7.1 每步验证流程

```
修改源码 → 编译 → 功能回归测试 → 性能回归测试 → commit
```

```bash
# 编译
cd USalign && g++ -O3 -ffast-math -lm -static -o USalign.exe USalign.cpp

# 功能回归（14 个用例）
cd scripts && python run_regression.py

# 性能回归（4 个用例 x 5 次）
cd scripts && python run_perf_test.py
```

### 7.2 性能验收标准

| 变化 | 判定 |
|------|------|
| < 20% | PASS |
| 20%-50% | WARNING（需分析原因） |
| > 50% | FAIL（回退或优化） |

如果 `Coords` 的连续内存布局改善了 cache 行为，预期性能**不退化**，甚至可能有微弱提升。

### 7.3 独立程序验证

阶段 5 之后需要重新运行 4 个独立程序的测试（TMscore/HwRMSD/MMalign/pdb2ss）。

## 8. 预计步骤统计

| 阶段 | 内容 | 预估步骤数 |
|------|------|-----------|
| 0: 基础设施 | 类型别名 + basic_fun.h 重载 | 3 |
| 1: 只读底层 | Kabsch + score_fun8 + make_sec | 4 |
| 2: 读写算法 | DP_iter + NWDP + se_main + TMscore 副本 | 6 |
| 3: 中层函数 | TMalign_main + SOIalign + MMalign + NWalign | 6 |
| 4: cpp 分配点 | 10 个 .cpp 文件 | 10 |
| 5: USalign.cpp | 4 个巨型函数 | 6 |
| 6: 清理 | 删除旧重载 + NewArray | 3 |
| **合计** | | **~38 步** |

## 9. 不改造的内容

- `pstream.h` — 第三方库
- `u[3][3]` — 栈上固定数组（作为 Kabsch 返回值），无需改
- `t[3]` — 同上
- `i_ali[]` — VLA（已在 L2-f 中转换为 vector）

## 10. 与之前里程碑的衔接

本方案（L2-h）是 C→C++ 重构计划的最后一个阶段（二级指针延后项）。前置条件全部满足：

- ✅ L0-L4 层所有 22 类 C→C++ 映射（除 printf 和二级指针外）已完成
- ✅ char* → string + FILE* → ifstream 里程碑已完成
- ✅ VLA → vector 已完成
- ✅ 独立程序回归测试框架已建立
- ✅ USalign-beta 分支 51 个 commit 基线稳定
