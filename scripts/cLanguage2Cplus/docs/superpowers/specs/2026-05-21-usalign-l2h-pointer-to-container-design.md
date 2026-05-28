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

## 2. 优化措施（按执行顺序）

本次改造不是简单的语法替换，而是以**提升缓存命中率**为目标的性能优化。以下按预估收益从大到小排列。

### 措施一：连续内存布局（核心）

**现状**：`NewArray` 逐行独立 `new[]`，n 个原子 = n+1 次堆分配。每行在堆上随机位置，即使顺序访问 `xa[0] → xa[1] → xa[2]`，硬件预取器也因地址不连续而完全失效。

**方案**：`Coords = vector<array<double,3>>` — 所有原子坐标在一个连续内存块中。Kabsch / score_fun8 / do_rotation 全部是严格顺序访问 `i=0..n-1`，连续布局下预取器可以提前加载后续原子，大幅降低 cache miss。同时消除一次指针间接（`double**` 需要指针数组→数据行两级跳转，`Coords` 直接计算偏移）。

**预期收益**：最大。坐标数组占总分配点 74%，覆盖全部热路径。

### 措施二：消除零初始化

**现状**：`NewArray` 内部 `new double[N]` 对原始类型不填零，分配即用。

**陷阱**：换成 `Coords xa(n)` 或 `xa.resize(n)` 会把 3n 个 double 全部填零（5000 原子 = 120KB 无意义写入），然后 `read_PDB` 再逐行覆盖——同一个位置写两遍。

**方案**：`xa.reserve(n)` 只分配不初始化，配合 `xa.push_back({x, y, z})` 聚合初始化直接写入，一次写入，零浪费。

**预期收益**：中等。消除 3n 次无意义内存写入，保持与 NewArray 行为一致。

### 措施三：临时缓冲区复用

**现状**：`TMalign_main` 等函数在入口一次性分配 `xtm`/`ytm`/`r1`/`r2` 等临时缓冲区，通过参数传给下游函数复用——当前设计上已经做到了复用。

**唯一例外**：`flexalign.h` 的 hinge 循环（≤9 次迭代）内每次 `NewArray(&xa_h, ...)`。换成 `Coords` 后，将声明移到循环外，循环内用 `clear() + push_back()` 复用同一块内存。

```cpp
// 旧：每次迭代分配
for (hinge = 0; hinge < h_opt; hinge++) {
    NewArray(&xa_h, xlen_h, 3);
    // ...
    DeleteArray(&xa_h, xlen_h);
}

// 新：复用缓冲区
Coords xa_h; xa_h.reserve(xlen_h);
for (hinge = 0; hinge < h_opt; hinge++) {
    xa_h.clear();  // 不释放 capacity
    for (...) xa_h.push_back({x, y, z});
    // ...
}
```

**预期收益**：小。绝大部分临时缓冲区当前已是复用模式，仅 flexalign hinge 循环受益。

### 措施四：编译优化选项

在 Makefile 中增加 `-march=native`，开启本机 CPU 支持的 AVX2/FMA 等指令集。编译器可以对热点循环（如 `dist()` 中的向量差分平方和）自动生成 SIMD 指令。零代码改动。

**预期收益**：中-高（取决于 CPU 代数）。不依赖容器改造，可独立评估。

### 不做

| 优化 | 原因 |
|------|------|
| DP 矩阵拍平为 1D | 收益有限（DP 不在最热路径），`score[i*stride+j]` 可读性差 |
| 缓存行对齐（`alignas(64)`） | 每个原子 24B 膨胀到 64B，L1 缓存能放的原子数减少 62%，反而降低命中率 |
| 多线程并行 | 单次 TMalign_main 内部依赖串行，无法并行；上层全对全比对可并行但不在本次范围 |
| `__restrict` / SIMD intrinsics | 可移植性差，编译器 `-march=native -O3 -ffast-math` 已经足够激进 |

---

## 3. 核心设计（类型定义与语法等价性）

### 3.1 类型定义

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

### 3.2 关键语法等价性

`xa[i][j]` 在 `double**` 和 `Coords&` 下语义完全相同，这是本方案的前提：

```cpp
// 旧代码
double **xa;
NewArray(&xa, n, 3);     // n+1 次堆分配，内存碎片化
xa[i][0] = x;             // OK
TMalign_main(xa, ya, ...);  // 传递
DeleteArray(&xa, n);      // 手动逐行释放

// 新代码
Coords xa;                // 不分配
xa.reserve(n);            // 唯一一次堆分配：连续内存块，不零初始化
xa.push_back({x, y, z});  // 聚合初始化，直接写入，不再触发分配
TMalign_main(xa, ya, ...);  // 传递（签名改为 Coords&）
// 自动析构，替代 DeleteArray
```

### 3.3 为什么必须用 `reserve + push_back` 而不是 `resize`

这是本方案最关键的性能优化点。

`Coords xa(n)` 或 `xa.resize(n)` 的行为：

1. 调用 n 次 `array<double,3>` 默认构造函数
2. 把 **3n 个 double 全部填零**（~120KB 对于 5000 原子结构）
3. 然后 `read_PDB` 再逐行覆盖写入 — **同一个位置写两遍**

而原始 `NewArray`（内部 `new double[N]`）对原始类型**不零填充**，分配的是未初始化的脏内存。

`reserve(n) + push_back()` 的行为：

```
Coords xa;
xa.reserve(n);   ← 分配连续内存块（n × 24 字节），不初始化
循环 n 次：
  xa.push_back({x, y, z});  ← 直接在已分配空间上原地构造，零浪费
```

- **1 次堆分配**（vs NewArray 的 n+1 次；vs resize 的 n+1 次 + 零填充）
- **无零填充**（vs resize 的 3n 次无意义写入）
- **连续内存**（vs NewArray 各行碎片化）

对于 DP 矩阵（DPMatrix 等），情况类似但稍复杂。二维矩阵用 `vector<vector<double>>` 每行独立分配，若要追求极致连续性可拍平为 `vector<double>`（见 2.5 节），但 DP 矩阵不在最热路径，可在后续阶段优化。

### 3.4 push_back 会多次触发扩容吗

不会。`reserve(n)` 确保 vector 的 `capacity >= n`，只要 push_back 次数不超过 n，就不会触发任何重新分配。每个 `push_back({x,y,z})` 只是在已分配好的连续内存上原地构造元素，与直接数组赋值开销相同。

### 3.5 函数签名转换对照

| 旧参数 | 新参数 | 索引语法 |
|--------|--------|---------|
| `double **xa`（坐标） | `Coords& xa` | `xa[i][j]` 不变 |
| `double **score`（DP） | `DPMatrix& score` | `score[i][j]` 不变 |
| `bool **path`（DP） | `PathMat& path` | `path[i][j]` 不变（值从 `true/false` 变为 `1/0`） |
| `int **S`（Gotoh） | `IntMat& S` | `S[i][j]` 不变 |
| `double **TMave_mat` | `DPMatrix& TMave_mat` | `TMave_mat[i][j]` 不变 |
| `double **ut_mat`（旋转） | `Rotation& ut_mat` | `ut_mat[i][j]` 不变 |
| `int **secx_bond`（SSE） | `Bond2& secx_bond` | `secx_bond[i][j]` 不变 |

### 3.6 为什么不使用模板化函数签名

Naïve 方案：
```cpp
template<typename T>
int TMalign_main(T& xa, T& ya, ...);
```

**不可行原因**：
- `TMalign_main` 约 500 行，`MMalign_search` 约 300 行——这些巨型函数作为模板会爆炸式增加编译时间
- 模板实例化放在头文件中会导致多个编译单元各自实例化，链接冲突
- `double**` 和 `Coords&` 虽然 `[i][j]` 语法相同，但其他操作（如 `xa = nullptr`、`DeleteArray`）差异巨大，模板实例化后会暴露这些差异

## 4. 执行策略：热函数直改 + 逐文件推进

### 3.1 核心策略

| 函数类型 | 策略 | 原因 |
|---------|------|------|
| **热函数**（Kabsch, score_fun8, do_rotation, read_PDB） | **直接改签名**，同步修所有调用者 | 被调用数百万次，桥接重载有间接开销；且调用者数可控 |
| **中温函数**（DP_iter, NWDP_TM, detailed_search 等） | 新增 `Coords&` 重载，旧 `double**` 版保留为包装器 | 调用者众多，分步迁移降低风险 |
| **冷函数**（TMave_mat, ut_mat） | 直接改签名 | 调用者少，无需桥接 |

### 3.2 为什么热函数不用反向桥接

以 `Kabsch` 为例，反向桥接的做法是：

```
Kabsch(double** x, ...) → 包装器（从 double** 临时构造 Coords 视图 → 调新重载）
Kabsch(Coords& x, ...)   → 真正实现
```

问题是包装器内部需要将 `double**` 的数据传递给 `Coords&` 参数，但 `double**` 不能直接传给 `Coords&`（类型不兼容）。如果做拷贝桥接，热点路径引入 O(n) 额外开销；如果做零拷贝视图，需要引入 `CoordView` 等新的基础设施。

**结论**：热函数不绕路，直接一步到位改签名 — 改函数体 + 改所有调用者，不保留旧版。Kabsch 的调用树经过之前 char* → string 重构后已非常清晰，调用者数可控。

### 3.3 直接改签名的执行模式

以 `Kabsch` 为例：

```
1. 改 Kabsch.h：签名 double** → const Coords&，函数体不变（xa[i][j] 语法完全兼容）
2. 修调用者：所有传 double** 的地方 → 传 Coords&
3. 如果调用者自己的参数也是 double**，递归向上改
4. 直到遇到"边界"——即 xa/ya 是从 read_PDB 分配出来的顶层变量
5. 此时 xa 本身从 double** → Coords，分配从 NewArray → reserve+push_back
6. 该文件改造完成，编译 + 回归测试
```

这是一个**自底向上的级联改造**，改一个函数就会带动其调用者一起改。与 printf→fcout 的逐个函数改造不同，这里需要按"调用链"推进。

## 5. 原子化执行步骤

### 设计原则

1. **每步一函数组**：一步只改一个文件的**一组关联函数**，改动量控制在可审查范围内
2. **自底向上**：先添加底层函数的 `Coords&` 重载，再逐层修改调用者
3. **双层并存**：`Coords&` 重载和旧的 `double**` 版本同时存在，编译器根据实参类型自动选择，零运行时开销
4. **逐步收窄**：当一个文件内所有调用者都切换到 `Coords&` 后，删除该文件内的旧 `double**` 版本
5. **每步验证**：编译 USalign.cpp → `run_regression.py`（14 用例全部 PASS）→ commit
6. **`const` 安全**：只读函数用 `const Coords&`，读写函数用 `Coords&`

### 调用链总览

```
main() / 顶层 .cpp 函数
  → TMalign_main()                     [分配 xtm,ytm,xt,r1,r2,score,path,val]
    → get_initial5() / get_initial_*()  [分配临时数组]
    → detailed_search()      [接收 xtm,ytm,xt]
      → TMscore8_search()    [接收 r1,r2,xtm,ytm,xt]
        → Kabsch()           [只读 r1,r2]
        → do_rotation()      [读 xtm, 写 xt]
        → score_fun8()       [只读 xt,ytm]
    → DP_iter()
      → NWDP_TM(), Kabsch()  [DP 矩阵 + 坐标]
```

热路径上 `xa[i][j]` 语法在 `double**` 和 `Coords&` 下完全等价——函数体不需要任何修改。

---

### 阶段 0：基础设施 — 类型别名

| 步骤 | 文件 | 内容 | 改动量 |
|------|------|------|--------|
| **L2h-00** | `basic_fun.h` | 添加 `Coords`、`DPMatrix`、`PathMat`、`IntMat`、`Rotation`、`Bond2` 类型别名（6 行 `using`），文件末尾 | 仅新增，零风险 |

**验证**：编译通过即可。

---

### 阶段 1：底层热函数 — 添加 Coords& 重载

这些是调用链最深处的只读函数，被数十个函数调用。只添加 `Coords&` 重载，**不删除也不修改**旧的 `double**` 版本。

| 步骤 | 文件 | 函数 | 参数变更 | 风险 |
|------|------|------|----------|------|
| **L2h-01** | `Kabsch.h` | `Kabsch()` | `double **x, double **y` → `const Coords& x, const Coords& y`（新重载） | **高**—被 ~25 处调用，需验证性能 |
| **L2h-02** | `TMalign.h` | `score_fun8()` + `score_fun8_standard()` | `double **xa, double **ya` → `const Coords& xa, const Coords& ya`（新重载） | 中—被 ~8 处调用 |
| **L2h-03** | `basic_fun.h` | `do_rotation()` + `transform()` | `double **x, double **x1` → `const Coords& x, Coords& x1`（新重载） | 低 |

**验证**：每步编译 USalign.cpp → `run_regression.py`

---

### 阶段 2：TMalign.h 中层 — Coords& 重载逐层上推

从调用 Kabsch/score_fun8 的函数开始，逐层添加 `Coords&` 重载。因为 `xa[i][j]` 语法相同，函数体完全不变——**纯签名复制**。

| 步骤 | 文件 | 函数组 | 内容 |
|------|------|--------|------|
| **L2h-04** | `TMalign.h` | `TMscore8_search()` + `TMscore8_search_standard()` | 新增 `Coords&` 重载，参数 `r1,r2,xtm,ytm,xt` → `Coords&`。函数体不变 |
| **L2h-05** | `TMalign.h` | `get_score_fast()` | 同上，`r1,r2` → `Coords&` |
| **L2h-06** | `TMalign.h` | `score_matrix_rmsd_sec()` | 新增 `Coords&` 重载 |
| **L2h-07** | `TMalign.h` | `detailed_search()` + `detailed_search_standard()` | 新增 `Coords&` 重载，`xtm,ytm,xt` → `Coords&` |
| **L2h-08** | `TMalign.h` | `get_initial5()` + `get_initial()` + `get_initial_fgt()` + `get_initial_ss()` + `get_initial_ssplus()` | 新增 `Coords&` 重载 |
| **L2h-09** | `TMalign.h` | `standard_TMscore()` | 新增 `Coords&` 重载 |

**验证**：每步编译 → `run_regression.py`。`USalign.cpp` 仍通过 `double**` 旧重载调用，所有测试应 PASS。

---

### 阶段 3：TMalign.h 顶层 — 坐标数组实际转换（方案 3）

> **2026-05-27 修订**：采用方案 3。DP 矩阵（`score`/`path`/`val`）统一延后——其 `vector<vector<T>>` 与 `NewArray` 产生的 `double**` 内存布局本质相同（逐行独立堆分配），转换收益仅限于消除手动 `DeleteArray`，但级联改动代价过大（7+ 函数、~15 个调用点，进一步传导到 NWDP_TM → NWalign.h）。跳过 DP 矩阵，聚焦坐标数组的连续内存收益。

#### L2h-10a：坐标临时数组 → Coords ✅ 已完成

`xtm`/`ytm`/`xt`/`r1`/`r2` 从 `NewArray(&xtm, minlen, 3)` → `Coords xtm; xtm.resize(minlen)`。调用下游函数时自动选中 `Coords&` 重载。

Commit: `721a39b`（"暂存"，待 push），改动文件：
- `TMalign.h`：`TMalign_main` 声明+分配 + 新增 `detailed_search_standard`、`DP_iter`、`clean_up_after_approx_TM` 的 Coords& 重载
- `basic_fun.h`：新增 `do_rotation(double**, Coords&, ...)` 重载

> **已知影响**：`-ffast-math` 下 14 个用例中 9 个出现 diff，根因为连续内存布局导致浮点舍入分歧。经分析确认非 bug，差异可接受（详见 `2026-05-27-msta-rna-diff-final-report.md`）。Baseline 暂不更新。

#### L2h-10a-收尾：fix `resize` → `reserve + push_back`

当前 commit 中 `xtm.resize(minlen)` 引入了不必要的零初始化（与 `NewArray` 的脏内存行为不一致）。改为：

```
Coords xtm; xtm.reserve(minlen);  // 分配，不填零
// 在填充循环中：xtm.push_back({x,y,z});
```

同理 `ytm`/`xt`/`r1`/`r2`。同时 `detailed_search_standard` 和 `DP_iter` 新增的 Coords& 重载中索引赋值（`xtm[k][0]=...`）需改为先 resize 或改用 push_back 模式。

| 子步骤 | 内容 | 风险 |
|--------|------|:--:|
| **L2h-10a-R1** | `TMalign_main` 中 `xtm/ytm/xt/r1/r2`：`resize` → `reserve`，填充循环改为 `push_back` | 低 |
| **L2h-10a-R2** | `detailed_search_standard(Coords&)` 填充模式改为 `push_back`（或前置 `resize`） | 低 |
| **L2h-10a-R3** | `DP_iter(Coords&)` 填充模式改为 `push_back`（或前置 `resize`） | 低 |

**验证**：编译 + `run_regression.py`（diff 数量应与收尾前一致，不新增）

#### L2h-10b：DP 临时矩阵 — 跳过 ⏭️

`score`/`path`/`val` 保持 `double**`/`bool**`/`double**`，`NewArray`/`DeleteArray` 不变。统一延后到「DP 矩阵独立阶段」。

#### L2h-10c：清理旧 double** 重载 — 延后 ⏭️

当前**无法删除任何旧重载**，调用者分布：

| 旧重载调用来源 | 涉及文件 | 说明 |
|---------------|---------|------|
| TMscore.h | `score_fun8`, `TMscore8_search`, `detailed_search` 同名独立副本 | 阶段 4 迁移后才能删 |
| MMalign.h | `TMalign_dimer_main`, `MMalign_search` 等 | 阶段 6 迁移后才能删 |
| 独立 .cpp | `TMalign.cpp`, `TMscore.cpp` 等的 `main()` | 阶段 8 迁移后才能删 |
| TMalign.h 内部 | `TMalign_main_standard` 等辅助函数 | 本文件内未迁移的调用者 |

旧重载作为兼容层保留，让未被迁移的调用者正常工作。统一在**阶段 10** 一次性批量清理。

---

### 阶段 4：TMscore.h 独立副本

TMscore.h 有与 TMalign.h **同名但独立实现**的函数（不同的 GDT/MaxSub 参数）。需单独处理。

> **方案 3**：只转换坐标数组，DP 矩阵（`score`/`path`/`val`）保留为 `double**`。

| 步骤 | 文件 | 内容 |
|------|------|------|
| **L2h-11** | `TMscore.h` | `score_fun8` + `score_fun8_standard` — 添加 `const Coords&` 重载 |
| **L2h-12** | `TMscore.h` | `TMscore8_search` + `TMscore8_search_standard` + `detailed_search` — 添加 `Coords&` 重载 |
| **L2h-13** | `TMscore.h` | `TMscore_main` — 转换 `xtm,ytm,xt,r1,r2` → Coords。旧 double** 重载保留（仍有外部调用者） |

**验证**：每步编译 USalign.cpp + `run_regression.py`。步骤 13 额外：`cd standalone/tmscore && python run_test.py`

---

### 阶段 5：其他算法头文件

逐个文件处理，每步独立。

> **方案 3**：SOIalign、flexalign、HwRMSD 只转换坐标数组。NWalign、se 纯 DP 矩阵，整体延后到 DP 矩阵独立阶段。

| 步骤 | 文件 | 内容 | 关键点 |
|------|------|------|--------|
| **L2h-14** | `SOIalign.h` | `getCloseK`、`soi_se_main`、`get_SOI_initial_assign`、`SOIalign_main` — 坐标数组 → Coords | 约 10 处 NewArray |
| **L2h-15** | `flexalign.h` | `flexalign_main` — 坐标数组 → Coords。**特别注意**：hinge 循环内 `xa_h/ya_h` 移到循环外，用 `clear()` 复用 | 约 6 处 NewArray + 缓冲区复用 |
| **L2h-16** | `HwRMSD.h` | `HwRMSD_main` + `Kabsch_Superpose` — `xt,r1,r2` → Coords | 约 3 处 NewArray |
| **L2h-17** | `NWalign.h` | ⏭️ 跳过。全文件为 DP 矩阵（`int**`），无坐标数组，延后到 DP 矩阵独立阶段 | — |
| **L2h-18** | `se.h` | ⏭️ 跳过。`se_main` 的 `score,path,val` 为 DP 矩阵，延后到 DP 矩阵独立阶段 | — |

**验证**：每步编译 + `run_regression.py`

> **2026-05-27 阻塞记录**：L2h-15（flexalign.h）和 L2h-16（HwRMSD.h）受阻于 `se_main` 无 Coords& 重载。级联链：`se_main(Coords&)` → `NWDP_SE(Coords&)`（NW.h 两个重载）。外部调用者 `TMalign_main(xa, ya)` 签名仍为 `double**`，进一步阻塞 flexalign.h 的 `xa_h`/`ya_h` 转换和 TMalign.cpp / TMscore.cpp 等独立 .cpp 文件。解除计划见下方「阻塞链解除计划」。

---

### 阻塞链解除计划（2026-05-27 制定）

两条阻塞链，按依赖顺序执行。

#### 阻塞链 A：se_main → NWDP_SE（解锁 flexalign.h + HwRMSD.h + se.cpp）

**代码分析**：

- **NW.h 两个 NWDP_SE**（行 192、271）：均只用 `dist(&x[i-1][0], &y[j-1][0])` 读取坐标。Coords 下 `&x[i-1][0]` 返回 `double*`，兼容现有 `dist(double*, double*)`。函数体零改动。
- **se.h se_main**（行 9-247）：函数体只用 `dist(&xa[i][0], &ya[j][0])` 和 `xa[i][0]` 读取坐标。`xa[i][j]` 在 `double**` 和 `const Coords&` 下语法等价。内部 DP 矩阵（score/path/val）保持 `double**`（Plan 3）。

**策略**：方向翻转 — Coords& 为真实现，double** 退化为 thin wrapper。

| 子步骤 | 文件 | 内容 | 风险 |
|--------|------|------|:--:|
| **A1** | NW.h | 两个 `NWDP_SE` 各新增 `const Coords&` 重载（只改 `x,y` 参数，函数体 copy-paste） | 低 |
| **A2** | se.h | `se_main` 签名 `double**` → `const Coords&`（238 行函数体零改动）；末尾新增 double** thin wrapper（从 double** 构造临时 Coords，调 Coords& 实现） | 中 — wrapper 有 O(n) 拷贝开销，但 se_main 不在最热路径 |
| **A3** | flexalign.h | `xt` → `Coords(resize)`，删 2 处 `DeleteArray(&xt, xlen)` | 低 |
| **A4** | HwRMSD.h | `xt` → `Coords(resize)` + `r1/r2` → `Coords(resize)`，删 2 处 `DeleteArray(&xt, xlen)` + 2 处 `DeleteArray(&r1/r2, minlen)`；`Kabsch_Superpose` 新增 Coords& 重载 | 低 |
| **A5** | se.cpp | `xa/ya` → Coords，`read_PDB` 自动选 Coords& 重载，`se_main` 自动选 Coords& 版 | 低 |

#### 阻塞链 B：TMalign_main / TMscore_main 外部签名（解锁 TMalign.cpp + TMscore.cpp 等）

**代码分析**：

- TMalign_main 内部坐标临时数组（xtm/ytm/xt/r1/r2）已是 Coords，但外部 `xa/ya` 参数仍为 `double**`
- TMalign_main 将 xa/ya 传给 ~8 个下游函数（`detailed_search`、`DP_iter`、`get_initial5` 等），这些函数的 Coords& 重载中 `x/y` 参数已保留为 `double**`
- 直接改 TMalign_main 签名 → 需同步改 ~8 个下游函数的 `x/y` 参数 → 级联太深

**策略**：桥接重载 — 新增 Coords& 重载，内部构建临时 `double**` 指针视图委托给原实现。O(n) 开销极小（~5K 指针/次），后续统一清理。

| 子步骤 | 文件 | 内容 | 风险 |
|--------|------|------|:--:|
| **B1** | TMalign.h | `TMalign_main` 新增 `const Coords& xa/ya` 重载：遍历 `xa/ya` 构建 `vector<double*>` 指针视图，调现有 double** 版 | 低 |
| **B2** | TMscore.h | `TMscore_main` 同上模式加 Coords& 桥接重载 | 低 |
| **B3** | TMalign.cpp | `xa/ya` → Coords，删 `NewArray`/`DeleteArray`，`read_PDB` + `make_sec` 自动选 Coords& 重载 | 低 |
| **B4** | TMscore.cpp | 同上 | 低 |
| **B5** | HwRMSD.cpp | `xa/ya` → Coords | 低 |

---

### 阶段 6：MMalign.h（最大的文件）

MMalign.h 有 31 处 `DeleteArray`，是多链比对的核心。函数多、调用链深，按函数拆步。

> **方案 3**：只转换坐标数组，DP 矩阵（`score`/`path`/`val`/TMave 矩阵）延后。

| 步骤 | 函数 | 改动 |
|------|------|------|
| **L2h-19** | `TMalign_dimer_main` | 坐标缓冲区 → Coords |
| **L2h-20** | `MMalign_search` | 链循环内 `xa/ya/xt` → Coords。**关键点**：循环内分配移至函数作用域，用 `clear()` 复用 |
| **L2h-21** | `MMalign_final` + `MMalign_se_final` | 同上模式 |
| **L2h-22** | `MMalign_dimer` + `MMalign_cross` | 同上 |
| **L2h-23** | `adjust_dimer_assignment` + `calMMscore` + `homo/hetero_refined_greedy_search` | 坐标数组 → Coords |
| **L2h-24** | `MMalign_iter` + `enhanced_greedy_search` | 坐标数组 → Coords（TMave 矩阵延后） |
| **L2h-25** | `parse_chain_list` | `xa` → Coords（调用 `read_PDB` 的 Coords& 重载） |

**验证**：每步编译 + `run_regression.py`。涉及 `-mm 1` 寡聚体比对路径的步骤额外跑 `standalone/mmalign`。

---

### 阶段 7：read_PDB 实际转换

至此所有 read_PDB 的调用者内部都已是 Coords。现在把 read_PDB 本身从写 `double**` 改为写 `Coords&`：

| 步骤 | 内容 |
|------|------|
| **L2h-26** | `basic_fun.h` `read_PDB` — 新增 `Coords&` 重载。内部用 `xa.clear(); xa.reserve(n); xa.push_back({x,y,z})` 替代 `xa[i][0]=x; xa[i][1]=y; xa[i][2]=z`。旧 `double**` 版保留 |

---

### 阶段 8：独立 .cpp 可执行文件

逐文件将顶层 `NewArray(&xa, n, 3)` 改为 `Coords xa; xa.reserve(n)`，配合新的 `read_PDB(Coords&)` 重载。

> **方案 3**：只转换坐标数组。`TMave_mat`、`ut_mat` 等矩阵延后。

| 步骤 | 文件 | 改动 | 额外验证 |
|------|------|------|---------|
| **L2h-27** | `TMalign.cpp` | `xa,ya` → Coords | — |
| **L2h-28** | `TMscore.cpp` | `xa,ya` → Coords | `standalone/tmscore` |
| **L2h-29** | `HwRMSD.cpp` | `xa,ya` → Coords | — |
| **L2h-30** | `MMalign.cpp` | `xa,ya` → Coords | `standalone/mmalign` |
| **L2h-31** | `se.cpp` | `xa,ya` → Coords | — |
| **L2h-32** | `qTMclust.cpp` | `xa,ya` → Coords | — |
| **L2h-33** | `pdb2ss.cpp` | `xa` → Coords | `standalone/pdb2ss` |
| **L2h-34** | `biounitasym.cpp` | `xa,ya` → Coords | — |

**验证**：每步编译 + `run_regression.py` + 对应独立程序测试。

---

### 阶段 9：USalign.cpp 主程序

> **方案 3**：只转换坐标数组。

| 步骤 | 函数 | 内容 |
|------|------|------|
| **L2h-35** | `TMalign()` | `xa,ya` → Coords。调用 `read_PDB(Coords&)` + `TMalign_main(Coords&)` |
| **L2h-36** | `MMalign()` + `MMdock()` | `xa,ya` → Coords |
| **L2h-37** | `mTMalign()` + `SOIalign()` + `flexalign()` | `xa,ya` → Coords |
| **L2h-38** | `search_databases()` + `main()` 中的数据库搜索路径 | `xa,ya` → Coords |

**验证**：每步编译 + `run_regression.py`（14 用例）+ `run_perf_test.py`

---

### 阶段 10：清理

| 步骤 | 内容 |
|------|------|
| **L2h-39** | 删除 `basic_fun.h` 中 `read_PDB`、`do_rotation` 的旧 `double**` 重载（确认零调用者） |
| **L2h-40** | 删除 `Kabsch.h` 中 Kabsch 的旧 `double**` 重载 |
| **L2h-41** | 删除 `NewArray` / `DeleteArray` 模板函数（确认全项目零调用者） |

**最终验证**：编译 USalign.cpp + 所有独立程序 + 全量回归测试 + 性能测试。

---

### 步骤汇总

| 阶段 | 步骤数 | 说明 |
|------|--------|------|
| 0: 基础设施 | 1 | 类型别名 |
| 1: 底层重载 | 3 | Kabsch, score_fun8, do_rotation |
| 2: TMalign.h 中层 | 6 | TMscore8_search → get_initial* |
| 3: TMalign.h 顶层 | 1 + 3 收尾 | L2h-10a 完成；收尾 fix resize→reserve |
| 4: TMscore.h | 3 | 独立副本（仅坐标数组） |
| 5: 其他算法头文件 | 4 | SOIalign, flexalign, HwRMSD（NWalign, se 延后） |
| 6: MMalign.h | 7 | 按函数拆分（仅坐标数组） |
| 7: read_PDB | 1 | read_PDB Coords& 重载 |
| 8: 独立 .cpp | 8 | 8 个独立可执行文件（仅坐标数组） |
| 9: USalign.cpp | 4 | 主程序（仅坐标数组） |
| 10: 清理 | 3 | 删除旧 double** 重载 + NewArray/DeleteArray |
| A: se_main 阻塞链 | 5 | 解锁 flexalign.h + HwRMSD.h + se.cpp |
| B: TMalign_main 阻塞链 | 5 | 解锁 TMalign.cpp + TMscore.cpp + HwRMSD.cpp |
| 11: DP 矩阵（延后） | ~8 | NWalign, se, MMalign DP 矩阵 + 全局清理残留 NewArray |
| **合计** | **~57 步** |（含阻塞链解除 + DP 矩阵独立阶段）|

> **方案 3 影响**：阶段 3~9 每步只转换坐标数组，DP 矩阵保持 `NewArray`/`DeleteArray`。阶段 10 清理时一次性删除所有旧坐标重载。DP 矩阵作为独立的阶段 11 统一处理。
> **阻塞链**：阶段 5 执行中发现 se_main → NWDP_SE 和 TMalign_main 外部签名的级联阻塞。阻塞链 A/B 采用方向翻转/桥接重载策略逐级击破。

## 6. 类型转换对照表

### 5.1 声明和分配

**坐标数组（Coords）— 最关键的性能优化**：

| 旧代码 | 新代码 |
|--------|--------|
| `double **xa;` | `Coords xa;` |
| `NewArray(&xa, n, 3);` | `xa.reserve(n);`（分配，不填零） |
| `xa[i][0] = x; xa[i][1] = y; xa[i][2] = z;` | `xa.push_back({x, y, z});`（聚合初始化，无零填充） |

> **重点**：不用 `xa.resize(n)` — 那会把 3n 个 double 全部填零再覆盖，而 NewArray 根本不填零。`reserve + push_back({x,y,z})` 行为等价于 NewArray（分配→直接写入），且只需 1 次堆分配（vs NewArray 的 n+1 次）。

**尺寸固定的数组（Bond2, Rotation）— 可用 resize**：

| 旧代码 | 新代码 |
|--------|--------|
| `int **secx_bond;` | `Bond2 secx_bond;` |
| `NewArray(&secx_bond, n, 2);` | `secx_bond.resize(n);` |

> Bond2 只有 2 个 int × n 个 SSE 片段，n 很小（几十），resize 的零初始化开销可忽略。

**DP 矩阵（DPMatrix, PathMat, IntMat）**：

| 旧代码 | 新代码 |
|--------|--------|
| `double **score;` | `DPMatrix score;` |
| `NewArray(&score, n+1, m+1);` | `score.assign(n+1, vector<double>(m+1));` |
| `bool **path;` | `PathMat path;` |
| `NewArray(&path, n+1, m+1);` | `path.assign(n+1, vector<char>(m+1));` |
| `int **S;` | `IntMat S;` |
| `NewArray(&S, n+1, m+1);` | `S.assign(n+1, vector<int>(m+1));` |
| `double **TMave_mat;` | `DPMatrix TMave_mat;` |
| `NewArray(&TMave_mat, c1, c2);` | `TMave_mat.assign(c1, vector<double>(c2));` |

> DP 矩阵每行独立分配（`vector<vector<T>>` 内部逐行 heap），与当前 NewArray 分配次数相同。若需极致连续性可后续拍平为 1D vector，但不阻塞本次改造。

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

## 7. 风险控制

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

## 8. 验证策略

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

## 9. 预计步骤统计

| 阶段 | 内容 | 步骤数 |
|------|------|--------|
| 0: 基础设施 | 类型别名 | 1 |
| 1: 底层热函数 | Kabsch + score_fun8 + do_rotation 的 Coords& 重载 | 3 |
| 2: TMalign.h 中层 | TMscore8_search → get_initial* 的 Coords& 重载 | 6 |
| 3: TMalign.h 顶层 | TMalign_main 坐标 + DP 矩阵实际转换 + 旧重载清理 | 3 子步 |
| 4: TMscore.h 独立副本 | score_fun8 → TMscore_main | 3 |
| 5: 其他算法头文件 | SOIalign(1) + flexalign(1) + HwRMSD(1) + NWalign(1) + se(1) | 5 |
| 6: MMalign.h 最大文件 | TMalign_dimer_main → parse_chain_list，按函数拆 7 步 | 7 |
| 7: read_PDB 转换 | basic_fun.h read_PDB 的 Coords& 重载 | 1 |
| 8: 独立 .cpp 入口 | TMalign/TMscore/HwRMSD/MMalign/se/qTMclust/pdb2ss/biounitasym | 8 |
| 9: USalign.cpp 主程序 | TMalign/MMalign/mTMalign+SOIalign+flexalign/search_databases | 4 |
| 10: 清理 | 删除旧 double** 重载 + NewArray/DeleteArray 模板 | 3 |
| **合计** | | **~44 步** |

## 10. 不改造的内容

- `pstream.h` — 第三方库
- `u[3][3]` — 栈上固定数组（作为 Kabsch 返回值），无需改
- `t[3]` — 同上
- `i_ali[]` — VLA（已在 L2-f 中转换为 vector）

## 11. 与之前里程碑的衔接

本方案（L2-h）是 C→C++ 重构计划的最后一个阶段（二级指针延后项）。前置条件全部满足：

- ✅ L0-L4 层所有 22 类 C→C++ 映射（除 printf 和二级指针外）已完成
- ✅ char* → string + FILE* → ifstream 里程碑已完成
- ✅ VLA → vector 已完成
- ✅ 独立程序回归测试框架已建立
- ✅ USalign-beta 分支 51 个 commit 基线稳定
