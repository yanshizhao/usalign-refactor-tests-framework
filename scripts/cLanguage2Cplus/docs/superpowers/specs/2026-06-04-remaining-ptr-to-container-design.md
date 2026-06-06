# 残余指针容器化改造方案：int* → vector + u[3][3]/t[3] → array

**日期**: 2026-06-04
**前置文档**: 
- `2026-05-21-usalign-l2h-pointer-to-container-design.md`（二级指针容器化方案）
- `2026-05-14-refactor-progress-log.md`（重构进度日志）
- `2026-05-21-refactor-final-summary.md`（重构最终总结）
**当前分支**: USalign-beta（HEAD `da40b66`，领先 master 252 commits）
**当前状态**: 全项目 `double**`/`char**`/`int**`/`bool**` 清零，`NewArray`/`DeleteArray` 清零

---

## 一、现状分析

### 1.1 全项目裸指针残存总览

| 指针类型 | 出现次数 | 最后一次审计 |
|:--------:|:--------:|:------------|
| `double**` | **0**（已清零 ✅） | 2026-06-03 |
| `char**` | **0**（已清零 ✅） | 2026-06-03 |
| `int**` | **0**（已清零 ✅） | 2026-06-03 |
| `bool**` | **0**（已清零 ✅） | 2026-06-03 |
| `NewArray`/`DeleteArray` | **0**（已清零 ✅） | 2026-06-03 |
| **`double t[3]` / `double u[3][3]`** | **~49 处** | 本次 |
| **`int*`（一级指针）** | **~97 处** | 本次 |
| **`char*`（一级指针）** | **~44 处** | 本次 |
| **`double*`（一级指针）** | **~12 处** | 本次 |

### 1.2 int* 详细分类

| 类别 | 数量 | 典型模式 | 内存管理 | 容器化方案 |
|:----|:----:|:---------|:---------|:----------|
| **invmap 映射数组** | ~40 | `int *invmap = new int[ylen+1];` → 读写 → `delete[] invmap;` | 手动 | `vector<int>` |
| **assign_list 链配对** | ~30 | `int *assign1_list` 函数参数 + `new/delete` 内部 | 手动 | `vector<int>&` / `vector<int>` |
| **i_ali 索引数组** | ~10 | `int i_ali[]` 在 TMscore 搜索中 | 自动（VLA已改vector） | 大部分已容器化 |
| **y2x/y2x0 初始映射** | ~10 | `int *y2x` 传递给 NWDP_TM | 手动 | `vector<int>&` |
| **sec_bond SSE边界** | ~5 | `int secx_bond[][]` 已被 `IntPairArray` 替代 | 自动 | **已容器化 ✅** |
| **k_ali 临时** | ~2 | 函数内局部临时数组 | 自动 | 已用 vector |

### 1.3 u[3][3]/t[3] 详细分类

| 类别 | 数量 | 典型模式 | 说明 |
|:----|:----:|:---------|:-----|
| **核心计算函数参数** | ~15 | `Kabsch(..., double t[3], double u[3][3])` | Kabsch、transform、do_rotation |
| **DP/NW 函数参数** | ~10 | `NWDP_TM(..., double t[3], double u[3][3])` | DP 迭代中的旋转矩阵 |
| **TMscore 函数参数** | ~10 | `TMscore8_search(..., double t0[3], double u0[3][3])` | TM-score 计算 |
| **局部变量声明** | ~14 | `double t[3], u[3][3]; //Kabsch rotation` | 各函数内局部变量 |

### 1.4 char* 现状（明确不做）

`const char *secx, *secy` 残留在计算热点中（NWDP_TM、get_initial_ss_dimer 等）。M 里程碑曾尝试改为 `string&`，但因 MinGW 桥接崩溃和 se_main 栈溢出问题而保留 `const char*`。

**结论：char* 系列本次不改**——风险高、收益低、有历史崩溃记录。

### 1.5 double* 现状（明确不做）

`double *rms`、`double *Rcomm` 等是输出单值参数，改为 `double&` 风格改善有限。`dist(double*, double*)` 是几何计算核心，入参已是 `const double*`，改 `array&` 需级联所有调用点，但函数体不变。

**结论：double* 系列本次不改**——12 处散落在各函数中，改造收益极低。

---

## 二、int* → vector<int> 改造方案

### 2.1 类型定义

在 `basic_fun.h` 中已有类型系统基础上，无需新增类型别名。直接使用 `std::vector<int>`。

### 2.2 核心模式转换

#### 模式 A：函数参数（输入/输出映射）

```cpp
// 旧
int TMscore8_search(..., int *invmap0, ...)  // invmap0 是输出参数
{
    int *invmap = new int[ylen + 1];
    // ... 计算 ...
    for (int i = 0; i < ylen; i++) invmap0[i] = invmap[i];
    delete[] invmap;
}

// 新
int TMscore8_search(..., vector<int>& invmap0, ...)
{
    vector<int> invmap(ylen + 1);
    // ... 计算 ...
    invmap0 = invmap;  // vector 赋值自动处理大小
}
```

#### 模式 B：局部动态数组

```cpp
// 旧
int *invmap = new int[ylen + 1];
// ... 使用 ...
delete[] invmap;

// 新
vector<int> invmap(ylen + 1);
// ... 使用 ...（自动析构）
```

#### 模式 C：函数参数（输入+输出，已预分配）

```cpp
// 旧
void NWDP_TM(..., int *y2x)  // y2x 是输出，长度 ylen
{
    for (int i = 0; i < ylen; i++) y2x[i] = -1;
}

// 新
void NWDP_TM(..., vector<int>& y2x)  // y2x 是输出
{
    y2x.assign(ylen, -1);
}
```

### 2.3 i_ali 的特殊情况

`int i_ali[]` 在 TMscore8_search 中作为函数参数，已在之前重构中改为 `vector<int>`。无需额外处理。

### 2.4 当前状态（2026-06-04 阶段性成果）

已完成：**全项目 `new int[]`/`delete[]` 清零，所有局部数组已用 `vector<int>`** ✅

仍存在的桥接层：

| 桥接类型 | 文件 | 说明 |
|:---------|:-----|:------|
| `vector<int>&` 重载 → `int*` 实现 | NW.h ×4, MMalign.h ×1 | 薄包装器，通过 `.data()` 委托给 `int*` 版 |
| `int*` 函数参数 + `.data()` 调用 | 全项目 ~40 函数 | 调用点用 `vec.data()` 传给仍持 `int*` 的函数 |

#### 核心调用链（int* 参数级联）

```
TMalign_main (local vector<int> invmap)
  → NWDP_TM(..., invmap)               vector<int>& overload ✅
  → get_initial(..., invmap.data())     .data() bridge  ← 需改函数签名
  → detailed_search(..., invmap.data()) .data() bridge  ← 需改函数签名
    → TMscore8_search(..., invmap.data())  .data() bridge ← 需改
      → get_score_fast(..., invmap)     .data() bridge ← 需改
      → NWDP_TM(..., invmap)            vector<int>& overload ✅
    → DP_iter(..., invmap)              .data() bridge ← 需改
  → standard_TMscore(..., invmap.data())  .data() ← 需改
  → approx_TM(..., invmap0.data())       .data() bridge ← 需改
  → se_main(..., invmap.data())         .data() bridge ← 需改
```

### 2.5 改造策略：瀑布翻转（自底向上）

**核心思想**：从调用链最底层函数开始，逐个将 `int*` 签名改为 `vector<int>&`，逐层向上波及。

```
翻转模式：
  1. 将 vector<int>& 桥接重载 → 真实现（复制算法体进去）
  2. 将 int* 版本 → 桥接（构造临时 vector，委托给 vector<int>& 版）
  3. 更新调用者：去掉 .data()，直接传 vector<int>
  4. 删除 int* 桥接版本
  5. 测试
```

#### 瀑布顺序

```
第 1 层：NWDP_TM / NWDP_TM_dimer / NWDP_SE（已有桥接）
  → 交换真/桥实现，删除 int* 版本

第 2 层：直接调用 NWDP 的函数
  → get_initial_ssplus / get_initial5 / get_initial_fgt
  → get_initial_ss_dimer / get_initial5_dimer
  → DP_iter / DP_iter_dimer
  → TMscore8_search / TMscore8_search_standard

第 3 层：调用第 2 层函数的函数
  → detailed_search / detailed_search_standard
  → get_initial / soi_egs / SOI_iter
  → standard_TMscore / approx_TM

第 4 层：调用第 3 层函数的函数
  → TMalign_main / TMalign_dimer_main
  → TMscore_main / SOIalign_main
  → flexalign_main / MMalign_search / MMalign_final
  → MMalign_iter / se_main / HwRMSD_main

第 5 层：MMalign 链配对函数
  → enhanced_greedy_search / homo_refined_greedy_search
  → hetero_refined_greedy_search / calMMscore
  → adjust_dimer_assignment / count_assign_pair
  → copy_chain_assign_data / MMalign_search(assign* params)
```

### 2.6 执行步骤详表

| 步 | 层 | 函数 | 文件 | 改动量估计 | 风险 |
|:-:|:--:|:-----|:----|:---------:|:----:|
| 1 | L1 | NWDP_TM(3版) + NWDP_SE 翻转 | NW.h | ~20行算法体搬移 | ⚠️ 中（算法体一致，翻后需测试） |
| 2 | L1 | NWDP_TM_dimer(CoordArray版) 翻转 | MMalign.h | ~30行 | ⚠️ 中 |
| 3 | L2 | get_initial_ssplus y2x0/y2x | TMalign.h | 1签名+1调用 | 低 |
| 4 | L2 | get_initial5 y2x | TMalign.h | 1签名+1调用 | 低 |
| 5 | L2 | get_initial_fgt y2x_ | TMalign.h | 1签名+1调用 | 低 |
| 6 | L2 | get_initial_ss_dimer y2x | MMalign.h | 1签名+1调用 | 低 |
| 7 | L2 | get_initial5_dimer y2x | MMalign.h | 1签名+1调用 | 低 |
| 8 | L2 | DP_iter invmap0 | TMalign.h | 1签名+4调用 | ⚠️ 中（热路径） |
| 9 | L2 | DP_iter_dimer invmap | MMalign.h | 1签名+1调用 | 低 |
| 10 | L2 | TMscore8_search invmap0 | TMalign.h / TMscore.h | 2签名+4调用 | ⚠️ 中 |
| 11 | L2 | TMscore8_search_standard invmap0 | TMalign.h / TMscore.h | 2签名+4调用 | ⚠️ 中 |
| 12 | L2 | get_score_fast invmap | TMalign.h | 1签名+6调用 | 低 |
| 13 | L3 | detailed_search invmap0 | TMalign.h | 1签名+8调用 | ⚠️ 中 |
| 14 | L3 | detailed_search_standard invmap0 | TMalign.h / TMscore.h | 2签名+4调用 | 低 |
| 15 | L3 | get_initial y2x | TMalign.h | 1签名+2调用 | 低 |
| 16 | L3 | soi_egs invmap | SOIalign.h | 1签名+4调用 | 低 |
| 17 | L3 | standard_TMscore invmap | TMalign.h / TMscore.h | 2签名+2调用 | 低 |
| 18 | L3 | approx_TM invmap0 (const) | TMalign.h | 1签名+3调用 | 低 |
| 19 | L4 | TMalign_main 移除 .data() | TMalign.h | ~20处.data()移除 | 低 |
| 20 | L4 | TMscore_main 移除 .data() | TMscore.h | ~8处.data()移除 | 低 |
| 21 | L4 | se_main invmap0 | se.h | 1签名+10调用 | ⚠️ 中（历史崩溃风险） |
| 22 | L5 | enhanced_greedy_search assign* | MMalign.h | 1签名+2调用 | 低 |
| 23 | L5 | 其他 assign* 函数 | MMalign.h | ~10签名+~20调用 | 低 |
| 24 | — | 删除所有桥接 `vector<int>&` 重载 | NW.h / MMalign.h | 删除4个桥接 | 低 |

### 2.7 关键函数详解

#### NWDP_TM 翻转（步 1）

当前：
```cpp
// int* 版（真实现，含算法体）
void NWDP_TM(..., int j2i[]) { ... }

// vector<int>& 版（桥接，委托给 int* 版）
void NWDP_TM(..., vector<int>& j2i) {
    NWDP_TM(..., j2i.data());    // 通过 .data() 委托
}
```

翻转后：
```cpp
// int* 版（桥接，委托给 vector<int>& 版）
void NWDP_TM(..., int j2i[]) {
    vector<int> j2i_view(j2i, j2i + len2 + 1);  // 构造视图
    NWDP_TM(..., j2i_view);
    // 可选：j2i_view 写回 j2i（如果 int* 版是输出参数）
}

// vector<int>& 版（真实现，含算法体）
void NWDP_TM(..., vector<int>& j2i) { ... }
```

> **注意**：NWDP_TM 的 `j2i` 是输出参数（函数内部写入），翻转时需要保证 `int*` 桥接也能正确输出。有两种方案：
> A. `int*` 版构造 `vector`，委托后 `std::copy` 写回
> B. `int*` 版直接改为容器版本的函数体（代码重复，但无拷贝开销）
> **推荐方案 B**：将当前 `int*` 版算法体复制到 `vector<int>&` 版，然后 `int*` 版退化为 `vector<int>` 构造 + 委托 + 写回。

### 2.5 关键语法等价性

```cpp
// 读操作：完全相同
int val = invmap[j];     // 旧
int val = invmap[j];     // 新（vector<int> 同样支持 operator[]）

// 写操作：完全相同
invmap[j] = -1;          // 旧
invmap[j] = -1;          // 新

// 作为函数参数传指针：不同
NWDP_TM(..., invmap);    // 旧：int* → 隐式转指针
NWDP_TM(..., invmap);    // 新：vector<int>& → 引用

// 取数据指针给第三方（极少见）
&invmap[j]               // 两者完全相同

// 获取大小
ylen（外部变量）         // 旧
invmap.size() - 1        // 新（可消除 ylen 参数）
```

### 2.6 消除冗余的 ylen 参数

`invmap` 数组的长度通常为 `ylen + 1`（或 `ylen`）。容器化后，函数内部可以通过 `y2x.size()` 获取大小，从而消除部分显式 `ylen` 参数。但为了最小化改动，建议**暂不消除 ylen 参数**，仅在函数体内部使用 `invmap.assign(ylen, -1)` 替代 `for` 循环清零。

### 2.7 风险控制

| 风险 | 说明 | 缓解措施 |
|:----|:-----|:---------|
| `vector` 扩容开销 | `int*` 是固定大小，`vector` 可能触发重新分配 | 统一用 `vector<int> v(N)` 或 `resize(N)`，确保一次性分配 |
| 跨函数引用语义变化 | `int*` 是传指针（可改原数组），`vector<int>&` 是传引用（等效） | 语义完全相同，只是语法改变 |
| `k_ali` 等特殊数组 | 部分 `int*` 同时用于存储索引和配对信息 | 逐函数审计，确认不是共用同一块内存的不同视图 |
| 性能退化 | `vector` 赋值有拷贝开销 | 热路径中改为 `swap` / `move` 避免拷贝 |

### 2.8 预估工作量

| 波次 | 修改量 | 测试风险 |
|:----:|:------:|:--------:|
| 第 1 波 | ~30 处 | 低（NWDP 函数体短，invmap 为纯输出） |
| 第 2 波 | ~80 处 | ⚠️ 中（TMscore8_search 在迭代热路径中，改引用不影响浮点） |
| 第 3 波 | ~90 处 | 低（assign_list 是链配对逻辑，不影响坐标计算） |
| **合计** | **~200 处** | |

---

## 三、u[3][3]/t[3] → std::array 改造方案

### 3.1 类型定义

在 `basic_fun.h` 中新增类型别名：

```cpp
// ============== Rotation & Translation Types ==============
using Vec3   = std::array<double, 3>;                    // 3D vector (translation)
using RotMat = std::array<std::array<double, 3>, 3>;     // 3×3 rotation matrix
using Transform = std::pair<Vec3, RotMat>;                // Optional: combined
```

### 3.2 核心语法等价性

```cpp
// === 读操作 ===
t[i]                       // double[3] 和 Vec3 完全相同
u[i][j]                    // double[3][3] 和 RotMat 完全相同

// === 写操作 ===
t[i] = 0.0;                // 完全相同
u[i][j] = 1.0;             // 完全相同

// === 初始化 ===
double t[3] = {0};         // 旧
Vec3 t = {};               // 新（zero-initialize）

double u[3][3] = {{0}};    // 旧
RotMat u = {};             // 新

// === 函数传参 ===
void f(double t[3], ...)   // 旧：t 退化为 double*
void f(Vec3& t, ...)       // 新：t 为引用

// === 取地址给第三方 ===
&t[0]                      // 完全相同（Vec3 内存连续）
&u[0][0]                   // 相同（RotMat 连续）
```

### 3.3 函数签名转换对照

| 旧参数 | 新参数 | 传参方式 |
|--------|--------|---------|
| `double t[3]` | `Vec3& t` | 引用（输出参数） |
| `const double t[3]` | `const Vec3& t` | const 引用（输入） |
| `double u[3][3]` | `RotMat& u` | 引用 |
| `const double u[3][3]` | `const RotMat& u` | const 引用 |
| `double t0[3]` → `double t[[3]]` | `Vec3& t0, Vec3& t` | 分离命名 |

### 3.4 核心函数改造清单

#### 基础设施（basic_fun.h + Kabsch.h）

| # | 函数 | 当前签名 | 新签名 |
|:-:|:----|:---------|:-------|
| 1 | `Kabsch` | `bool Kabsch(..., double *rms, double t[3], double u[3][3])` | `..., double& rms, Vec3& t, RotMat& u)` |
| 2 | `transform` | `void transform(double t[3], double u[3][3], double *x, double *x1)` | `void transform(const Vec3& t, const RotMat& u, const Vec3& x, Vec3& x1)` |
| 3 | `do_rotation` | `void do_rotation(CoordArray& x, CoordArray& x1, int len, double t[3], double u[3][3])` | `..., const Vec3& t, const RotMat& u)` |

> **注意**：`transform` 和 `do_rotation` 在计算热路径中高频调用（Kabsch 迭代内），`Vec3` 和 `RotMat` 均通过 const 引用传递，避免拷贝。

#### TMalign.h 搜索函数

| # | 函数 | 改动 |
|:-:|:----|:-----|
| 4-13 | `TMscore8_search` / `TMscore8_search_standard` / `detailed_search*` / `DP_iter` / `standard_TMscore` / `get_initial*` | 所有 `double t0[3], double u0[3][3]` → `Vec3& t0, RotMat& u0` |

#### MMalign.h / flexalign.h / SOIalign.h / NW.h

| # | 函数 | 改动 |
|:-:|:----|:-----|
| 14-20 | `MMalign_search` / `flexalign_main` / `SOIalign_main` / `NWDP_TM_dimer` 等 | 同上 |

#### 调用方局部变量

```cpp
// 旧
double t[3], u[3][3]; //Kabsch translation vector and rotation matrix
// ...
Kabsch(r1, r2, n_ali8, 0, &rmsd0, t, u);

// 新
Vec3 t; RotMat u;
// ...
Kabsch(r1, r2, n_ali8, 0, rmsd0, t, u);
```

### 3.5 与 int* 改造的依赖关系

两个改造**相互独立**，无依赖关系。可以并行或分先后执行。

### 3.6 风险控制

| 风险 | 说明 | 缓解措施 |
|:----|:-----|:---------|
| **浮点分歧** | `double[3]`（栈上连续）vs `Vec3`（array 包装）的内存布局完全一致，但函数传参方式从指针退化为引用传递 | 编译器对引用的别名分析不同于指针，可能在 `-ffast-math` 下产生浮点差异。**但差异应远小于 Kabsch 的 double** → CoordArray 改造** |
| **double* rms 输出** | 函数同时需要改 `double *rms` → `double& rms` | 可在同一波次完成 |
| **transform 的 double* x 参数** | `double *x, double *x1` 是单点坐标（3 doubles），可改为 `const Vec3& x, Vec3& x1` | 改后调用点需从 `&xa[i][0]` 改为 `xa[i]` |

### 3.7 执行步骤

#### 步骤 A：类型定义 + basic_fun.h/Kabsch.h（~3 个函数 + 所有调用点）

```
1. basic_fun.h 添加 Vec3/RotMat 类型别名
2. Kabsch.h 添加 Vec3&/RotMat& 重载（保留旧版本做桥接）
3. basic_fun.h transform/do_rotation 添加重载
4. 逐个迁移 Kabsch 调用点（22 处已有经验）
5. 迁移 transform/do_rotation 调用点
```

#### 步骤 B：TMalign.h 搜索函数 + 调用点（~10 个函数）

```
6. TMscore8_search 等函数添加 Vec3&/RotMat& 重载
7. 逐函数翻转（类似 Kabsch 22 处模式）
```

#### 步骤 C：MMalign.h + 其他文件（~7 个函数）

```
8. MMalign.h/flexalign.h/SOIalign.h/NW.h 逐个改签名
```

---

## 四、总结与建议

### 4.1 执行顺序

```
Option A: int* → vector 先做（推荐）
  原因: 安全（无浮点风险）、收益高（消除手动new/delete）
  
Option B: u[3][3] → array 先做
  原因: 改动量小（~150处 vs ~200处），但浮点分歧需额外测试
  
Option C: 两项并行推进
  不推荐: 同时修 ~350 处，排查问题难度倍增
```

### 4.2 预估总工作量

| 改造项 | 文件数 | 函数签名改 | 调用点改 | 总计修改 | 预估时间 |
|:------|:-----:|:---------:|:--------:|:--------:|:--------:|
| int* → vector | ~8 | ~24 | ~180 | ~200处 | 2-3 天 |
| u[3][3] → array | ~10 | ~20 | ~130 | ~150处 | 2-3 天 |
| **合计** | | | | **~350处** | **4-6 天** |

### 4.3 建议路线

```
当前 (252 commits ahead of master)
  → int* → vector<int> 改造（第1-3波，每波测试+提交）
  → u[3][3]/t[3] → Vec3/RotMat 改造（步骤A-C）
  → 更新3个baseline（msta_rna/all_vs_all/database_search）
  → 合并回 master
```

> **关键原则**：每个函数新增容器重载后，逐调用点翻转，每步测试通过后再提交。参照本次 Kabsch 22 处逐一测试的模式。

---

## 2026-06-04 执行总结

### 已完成工作量

| 阶段 | 内容 | 步数 | 状态 |
|:----|:-----|:----:|:----:|
| **L0** | 全项目 `new int[]` → `vector<int>`，消除所有手动 `new[]`/`delete[]` | 15 | ✅ |
| **L1** | NWDP_TM/NWDP_SE/NWDP_TM_dimer 翻转（`vector<int>&` 为真实现） | 4 | ✅ |
| **L2** | 下级函数签名更新（`get_initial*`/`DP_iter*`/`get_score_fast` 等） | 8 | ✅ |
| **L3** | 中级函数签名更新（`get_initial`/`standard_TMscore`/`approx_TM`/`soi_egs`） | 4 | ✅ |
| **L4** | 顶层函数签名更新（`detailed_search*`/`score_matrix_rmsd_sec`/`get_initial_ss`） | 4 | ✅ |
| **L5a** | 链配对函数（`enhanced_greedy_search`/`count_assign_pair`/`calMMscore` 等） | 3 | ✅ |
| **L5b** | MMalign 全套（`MMalign_search`/`MMalign_final`/`MMalign_iter`/`copy_chain_assign_data` 等） | 6 | ✅ |
| **L5c** | `se_main` 翻转 + 全部 9 处调用点迁移 + 删除 `int*` 桥接 | 3 | ✅ |
| **L5d** | SOIalign 全套（`soi_se_main`/`SOI_iter`/`SOI_assign2super`/`SOIalign_main`） | 4 | ✅ |
| **总计** | **~350 处函数签名/调用点修改** | **51 commits** | ✅ |

### 关键经验

| # | 经验 | 说明 |
|:-:|:-----|:------|
| 1 | **瀑布翻转策略** | 从调用链底层开始翻，逐层向上波及，每层测试通过后再推进 |
| 2 | **逐个测试** | 每个函数变更后编译→回归测试→删除冗余→提交，避免大规模改动难以定位问题 |
| 3 | **前向声明** | 当 `int*` 桥接调用 `vector<int>&` 版时，需要前向声明后者 |
| 4 | **双向拷贝桥接** | `NWDP_SE` 等函数中 `int*` 参数既是输入又是输出，`int*` 桥接需双向拷贝 |
| 5 | **变量作用域** | `se.h` 和 `SOIalign.h` 中 `if` 块内 `vector<int>` 声明与外层 `int*` 声明重名导致变量隐藏——需要同时清理外层的旧声明 |
| 6 | **CRLF 行尾** | Windows 下文件有 `^M` 行尾，Edit tool 匹配时需注意 |
| 7 | **`double*`/`char*` 保留合理** | `dist()`/`transform()` 等几何热路径和 `make_sec()` 等二级结构函数保留指针参数，改动收益低 |

### 当前项目状态

| 指标 | 值 |
|:----|:----:|
| 领先 master | **~330 commits** |
| `new[]` / `delete[]` | **零** ✅ |
| `int*` | **零** ✅（仅 `find_max_frag` 2个输出单值改为`int&`）|
| `double*`（非const） | **零** ✅ |
| `char*`（非argv, 非const） | **零** ✅ |
| `double**` / `int**` / `char**` / `bool**` | **零** ✅ |
| `int*` 逆向桥接 | 全部删除 ✅ |
| `reinterpret_cast` | **零** ✅ |
| Vec3/RotMat 类型别名 | 已添加 ✅ |
| Vec3/RotMat 重载 | transform/do_rotation/Kabsch/NWDP_TM/NWDP_TM_dimer/get_score_fast/calMMscore ✅ |
| 已迁移 Vec3/RotMat 调用者 | adjust_dimer/homo/hetero_refined/get_initial5 ✅ |
| 回归测试 | 11P+3F（3 FAIL 为已知 `-ffast-math` 浮点符号噪声） |

### 已完成清理（2026-06-05 全日）

| 阶段 | 内容 | Commits |
|:----|:------|:-------:|
| **P0** | 核心代码 `int*` 清零 + NWDP_TM_dimer翻转 + 局部变量vector化 | `6ff2e77` |
| **P1** | 独立程序 `int*` 清零 + `.data()`移除 | `9f5d437` |
| **double*** | 清理 `new double[]/delete[]` | `a9c50cc` |
| **桥接** | 删除6个 `int*` 逆向桥接 | `530015e` |
| **char*/string** | `make_sec` char*→string& + MMalign链char*→string& | `bbdea39`~`80cfb11` |
| **double*升级** | Kabsch/score_fun8/TMscore8_search rms→double& + dist_list→vector& | `5a0392e`~`675a61d` |
| **P4 Vec3/RotMat** | 类型别名 + 7个核心函数Vec3重载 + 4个调用者迁移 | `c9bf65e`~`24f1ff7` |

### 下一步（P4 剩余）

剩余约 **11 个函数**需要添加 Vec3/RotMat 重载才能完成全部迁移：

| 函数 | 文件 |
|:-----|:-----|
| `detailed_search` / `detailed_search_standard` | TMalign.h |
| `standard_TMscore` / `approx_TM` | TMalign.h |
| `DP_iter` / `get_initial_fgt` / `get_initial_ssplus` | TMalign.h |
| `CPalign_main` / `copy_t_u` | TMalign.h |
| `get_initial5_dimer` | MMalign.h |
| `SOI_iter` / `get_SOI_initial_assign` / `SOI_assign2super` | SOIalign.h |
| **TMalign.h:993** | `find_max_frag(start, end)` | 输出单值（非数组，可保留） |
| **flexalign.h:37** | `aln2invmap(invmap)` | 工具函数 |
| **se.h:31-32** | `m1=nullptr; m2=nullptr` | 影子变量需清理 |
| **SOIalign.h:7** | `print_invmap(invmap)` | 调试输出 |

### 三波执行计划（2026-06-06 更新）

整体策略：**分波次推进**，每波 3-5 个函数，每步独立编译验证。

#### 当前已有 Vec3/RotMat 重载

| 函数 | 文件 | 状态 |
|:-----|:----|:----:|
| `Kabsch` | Kabsch.h | ✅ |
| `transform` / `do_rotation` | basic_fun.h | ✅ |
| `NWDP_TM` / `NWDP_TM_dimer` | NW.h / MMalign.h | ✅ |
| `get_score_fast` / `calMMscore` | TMalign.h / MMalign.h | ✅ |
| `copy_t_u` / `approx_TM` | TMalign.h | ✅ 第 1 波预加 |

#### 第 1 波：叶子函数（无子依赖或子依赖已有重载）

| 波次 | # | 函数 | 位置 | 大小 | 子调用依赖 |
|:----:|:-:|:-----|:----:|:----:|:----------|
| 1a | 1 | `TMscore8_search` | TMalign.h:86-247 | 162行 | `Kabsch`✅ `do_rotation`✅ |
| 1a | 2 | `TMscore8_search_standard` | TMalign.h:251-412 | 162行 | 同上 |
| 1a | 3 | `get_initial` | TMalign.h:654-682 | 29行 | `get_score_fast`✅ |
| 1b | 4 | `detailed_search` | TMalign.h:422-444 | 23行 | `TMscore8_search`(#1) |
| 1b | 5 | `detailed_search_standard` | TMalign.h:447-471 | 25行 | `TMscore8_search_standard`(#2) |
| 1b | 6 | `standard_TMscore` | TMalign.h:2941-2980 | 40行 | `Kabsch`✅ `TMscore8_search_standard`(#5) |

#### 第 2 波：中层函数

| # | 函数 | 位置 | 大小 | 子调用依赖 |
|:-:|:-----|:----:|:----:|:----------|
| 7 | `DP_iter` | TMalign.h:1364-1415 | 52行 | `NWDP_TM`✅ `TMscore8_search`(#1) |
| 8 | `get_initial_fgt` | TMalign.h:1121-1358 | 238行 | `get_score_fast`✅ `find_max_frag`(无t/u) |

#### 第 3 波：入口函数迁移（已完成 ✅）

| 步骤 | 内容 | 状态 |
|:----:|:-----|:----:|
| TMalign_main | 签名+局部变量 Vec3/RotMat 化 | ✅ |
| CPalign_main / SOIalign_main / flexalign_main | 同上 | ✅ |
| USalign.cpp / MMalign.h 调用者迁移 | 同上 | ✅ |
| 全部 double[] 旧版删除 | 1885 行清理 | ✅ |

---

### 最终阶段：全局 double[] 清零（2026-06-06 更新）

**目标**：删除源码中所有 `double t[3]`/`double t0[3]` / `double u[3][3]`/`double u0[3][3]` 函数参数

#### 依赖关系

```
flexalign.h 输出函数 → basic_fun.h (transform/do_rotation)
                    → t_u2tu/tu2t_u
TMscore.h (独立程序)
HwRMSD.h (独立程序)
```

#### 执行顺序

| 波次 | # | 文件 | 函数 | 改动量 | 说明 |
|:----:|:-:|:----|:-----|:-----:|:-----|
| **1a** | 1 | flexalign.h | `output_flexalign_rotation_matrix` | ~15行 | 输出函数，改签名 `double[]`→`const Vec3&,const RotMat&` |
| **1b** | 2 | flexalign.h | `output_flexalign_pymol`（声明+定义） | ~50行×2 | 含 `transform(t,u,x,x1)`，内部 x/x1 需改 `Vec3` |
| **1c** | 3 | flexalign.h | `output_flexalign_rasmol`（声明+定义） | ~50行×2 | 同上 |
| **1d** | 4 | flexalign.h | `output_flexalign_results` | ~80行 | 调用上述函数 |
| **1e** | 5 | flexalign.h | `t_u2tu(double[])` / `tu2t_u(double[])` | ~20行 | 已有 Vec3 重载 ✅，直接删旧版 |
| **2** | 6 | basic_fun.h | `transform(double[])` / `do_rotation(double[])` | ~15行 | flexalign 已迁移，无调用者 |
| **3** | 7 | Kabsch.h | `Kabsch(double[])` | ~150行 | 无调用者 |
| **4** | 8 | NW.h | `NWDP_TM(double[])` 声明+定义 | ~80行 | 无调用者 |
| **5** | 9 | TMscore.h | 5 处 double[] 签名 | ~30行 | 独立程序，同步升级 |
| **6** | 10 | HwRMSD.h | 2 处 double[] 签名 | ~20行 | 独立程序，同步升级 |

#### 每步执行流程

```
1. 改签名（纯类型变更：double t[3] → const Vec3& t, double u[3][3] → const RotMat& u）
2. 局部变量同步（double[3] → Vec3，double[3][3] → RotMat）
3. 编译验证
4. 回归测试（run_regression.py）
5. 提交
```
