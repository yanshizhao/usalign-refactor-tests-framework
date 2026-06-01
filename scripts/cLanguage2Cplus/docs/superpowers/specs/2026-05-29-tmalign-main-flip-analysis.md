# TMalign_main 方向翻转：架构设计与问题分析

**日期**: 2026-05-29
**当前分支**: USalign-beta（102 commits 领先 master）
**当前 HEAD**: `75c564c` refactor(TMalign_main): 添加 Coords& 前向声明 + 混合桥接优化 + get_initial_fgt 修复
**测试基线**: 已移除 `-ffast-math`，14/14 ALL PASS

---

## 一、问题背景

L2-h 阶段将全项目坐标数组从 `double**`（NewArray 逐行独立 new[]，碎片化堆分配）转换为 `Coords`（`std::vector<std::array<double,3>>`，连续内存）。但核心算法函数 `TMalign_main` 的函数签名仍为 `double**`，子函数调用也仍使用 `double**` 重载。

目标是：将 `TMalign_main` 的函数签名改为 `Coords&`，使所有子函数调用也使用 Coords& 重载，彻底消除二级指针。

---

## 二、当前架构（桥接模式）

```
                    ┌──────────────────────────────┐
                    │  USalign.cpp TMalign()       │
                    │  xa/ya = Coords              │
                    └──────────┬───────────────────┘
                               │ TMalign_main(xa, ya, ...)
                               ▼
          ┌─────────────────────────────────────────┐
          │  TMalign_main(Coords&, Coords&, ...)    │
          │  [桥接体，~30 行]                        │
          │                                        │
          │  vector<double*> xa_view(xlen);         │
          │  for (...) xa_view[i] = xa[i].data();   │
          │  vector<double*> ya_view(ylen);         │
          │  for (...) ya_view[i] = ya[i].data();   │
          │  return TMalign_main(xa_view.data(),    │
          │      ya_view.data(), ...);              │
          └──────────┬──────────────────────────────┘
                     │ 委托给 double** 版
                     ▼
┌──────────────────────────────────────────────────────┐
│  TMalign_main(double**, double**, ...)               │
│  [真实现，持有算法体，~600 行]                        │
│                                                      │
│  double **score; bool **path; double **val;          │
│  Coords xtm, ytm, xt, r1, r2;                       │
│                                                      │
│  get_initial(..., xa, ya, ...)    → double** 重载    │
│  detailed_search(..., xa, ya, ...) → double** 重载   │
│  DP_iter(..., xa, ya, ...)       → double** 重载     │
│  Kabsch(r1, r2, ...)             → double** SVD      │
│  do_rotation(xa, xt, ...)        → basic_fun.h:880   │
│                                  (double**, Coords&)  │
│  ...                                                  │
│  return 0;                                            │
└──────────────────────────────────────────────────────┘
```

### 混合桥接（CPalign 路径）

```
TMalign_main(Coords& xa, double** ya, ...)  [混合桥接]
  → 构造 Coords ya_tmp → TMalign_main(xa, ya_tmp, ...)
  → 委托 Coords& 桥接 → double** 真实现
```

---

## 三、目标架构（翻转后）

```
                    ┌──────────────────────────────┐
                    │  USalign.cpp TMalign()       │
                    │  xa/ya = Coords              │
                    └──────────┬───────────────────┘
                               │ TMalign_main(xa, ya, ...)
                               ▼
┌──────────────────────────────────────────────────────┐
│  TMalign_main(Coords&, Coords&, ...)                 │
│  [真实现，持有算法体，~600 行]                        │
│                                                      │
│  double **score; bool **path; double **val;          │
│  Coords xtm, ytm, xt, r1, r2;                       │
│                                                      │
│  get_initial(..., xa, ya, ...)    → Coords& 重载     │
│  detailed_search(..., xa, ya, ...) → Coords& 重载    │
│  DP_iter(..., xa, ya, ...)       → Coords& 重载      │
│  Kabsch(r1, r2, ...)             → Coords& SVD       │
│  do_rotation(xa, xt, ...)        → basic_fun.h:872   │
│                                  (Coords&, Coords&)  │
│  ...                                                  │
│  return 0;                                            │
└──────────────────────────────────────────────────────┘
                     ▲
                     │ 委托给 Coords& 版
          ┌──────────┴──────────────────────────────┐
          │  TMalign_main(double**, double**, ...)   │
          │  [薄包装器，~25 行]                      │
          │                                         │
          │  Coords xa_tmp, ya_tmp;                 │
          │  for (...) xa_tmp.push_back({...});      │
          │  for (...) ya_tmp.push_back({...});      │
          │  return TMalign_main(xa_tmp, ya_tmp,     │
          │      ...);                               │
          └──────────────────────────────────────────┘
```

### 调用链变化

| 调用来源 | 当前（桥接） | 翻转后 |
|---------|-------------|--------|
| USalign.cpp xa/ya=Coords | 桥接 → double** 真实现 | **Coords& 真实现** |
| MMalign.h xa/ya=double** | double** 真实现（直接） | double** 包装器 → Coords& |
| flexalign.h xa/ya=double** | double** 真实现（直接） | double** 包装器 → Coords& |
| qTMclust.cpp xa/ya=double** | double** 真实现（直接） | double** 包装器 → Coords& |

---

## 四、翻转操作步骤

### 4.1 前置条件（已完成）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1 | 前向声明 | TMalign.h | `TMalign_main(Coords&, Coords&, ...)` 在 `double**` 版之前声明 |
| 2 | `approx_TM(Coords&)` 重载 | TMalign.h | 新增，`(double*)&xa[i][0]` const_cast |
| 3 | `get_initial_ssplus(Coords& x/y)` 重载 | TMalign.h | 新增，body 零改动 |
| 4 | `get_initial_fgt` bug 修复 | TMalign.h | 3 个预存 bug（堆溢出、init 值、缺失逻辑） |
| 5 | 混合桥接更新 | TMalign.h | 直接委托 Coords& 真实现，避免双重拷贝 |

### 4.2 核心翻转（3 步）

#### 步骤 A：Coords& 桥接体 → 算法体

```
old_string = 桥接体（~30 行）
  {
      vector<double*> xa_view(xlen);
      vector<double*> ya_view(ylen);
      for (...) xa_view[i] = xa[i].data();
      for (...) ya_view[i] = ya[i].data();
      return TMalign_main(xa_view.data(), ya_view.data(), ...);
  }

new_string = 算法体（~600 行，从 double** 版复制，加 // [Coords& true implementation] 标记）
  {
      double D0_MIN; double Lnorm; ...
      double **score; bool **path; double **val;
      Coords xtm, ytm, xt, r1, r2;
  // [Coords& true implementation]
      ...
      return 0;
  }
```

#### 步骤 B：double** 算法体 → 薄包装器

```
old_string = 算法体（~600 行）
new_string = 包装器（~25 行）
  {
      Coords xa_tmp; xa_tmp.reserve(xlen);
      for (...) xa_tmp.push_back({xa[i][0], xa[i][1], xa[i][2]});
      Coords ya_tmp; ya_tmp.reserve(ylen);
      for (...) ya_tmp.push_back({ya[i][0], ya[i][1], ya[i][2]});
      return TMalign_main(xa_tmp, ya_tmp, ...);
  }
```

#### 步骤 C：混合桥接体更新

```
old_string = { vector<double*> xa_view(xlen); for (...) xa_view[i]=(double*)xa[i].data();
               return TMalign_main(xa_view.data(), ya, ...); }
new_string = { Coords ya_tmp; ya_tmp.reserve(ylen);
               for (...) ya_tmp.push_back({ya[i][0], ya[i][1], ya[i][2]});
               return TMalign_main(xa, ya_tmp, ...); }
```

---

## 五、遇到的问题

### 5.1 现象

翻转后运行回归测试，即使去掉 `-ffast-math`，结果仍与 baseline 不同：

| 测试用例 | 桥接版（baseline） | 翻转版 | 差异 |
|---------|:--:|:--:|:--:|
| standard_protein | aligned_len=143, TM=0.81453 | aligned_len=144, TM=0.75239 | **7.6%** |
| oligomer | 链映射 B:G:D:C:H:F:A:E | 链映射 E:F:A:C:G:H:D:B | **完全不同的链配对** |
| multichain_split | aligned_len=63 | aligned_len=55 | **12.7%** |
| fully_non_seq | aligned_len=108 | aligned_len=98 | **9.3%** |
| all_vs_all | aligned_len=75, TM=0.50577 | aligned_len=55, TM=0.35596 | **29.6%** |

### 5.2 排查过程

| 假设 | 验证方法 | 结论 |
|------|---------|------|
| `-ffast-math` 导致浮点差异 | 去掉 `-ffast-math` 编译 | ❌ 差异仍在 |
| 编译器优化级别影响 | `-O0` 无优化编译 | ❌ 差异仍在 |
| Coords& 重载有代码差异 | 逐行比对 14 个重载 vs double** 版 | ✅ 全部为忠实拷贝（仅格式化差异） |
| `do_rotation` 数值不同 | 单独测试两种重载的数值输出 | ✅ `max_diff = 0`（完全相同） |
| `dist` 数值不同 | 代码审查 | ✅ 计算式完全相同 |
| 某子函数有预存 bug | 修复 `get_initial_fgt` 3 个 bug | ❌ 修复后差异仍在 |

### 5.3 根因分析

**所有子函数的 Coords& 重载在源代码层面与 double** 版本完全等价。** 差异的根因是编译器对两种内存访问模式生成不同的机器码：

| 表达式 | double** 版本 | Coords& 版本 |
|--------|-------------|-------------|
| `xa[i][0]` | `*(*(xa+i)+0)` — 两次解引用 | `xa.operator[](i).operator[](0)` — 两次 `vector`/`array` 索引 |
| `&xa[i][0]` | `xa[i]`（从指针数组取值） | `xa[i].data()`（获取 embedded array 地址） |
| `do_rotation(xa, xt)` | 选行 880：`&x[i][0]` 取值 | 选行 872：`x[i].data()` 取值 |

虽然**每个单独操作的数值结果一致**，差异在于：

1. **Kabsch SVD 是迭代算法**（数百万次浮点运算）
2. 不同的机器码导致**寄存器分配不同**
3. 在 SVD 迭代中，不同的中间值暂存方式导致**浮点舍入逐轮累积**
4. 累积到第 10-11 位小数时，刚好跨过了 Kabsch 的**旋转矩阵判定边界**
5. 不同的旋转矩阵 → **不同的残基配对选择** → **完全不同的比对路径**

这就是为什么标准蛋白比对出现 7.6% 的 TM-score 变化，而寡聚体比对出现了**完全不同的链映射**——初始偏差在选择点被级联放大了。

### 5.4 与已知 L2-h 差异的关系

L2-h 阶段（坐标数组 `double**` → `Coords`）已经产生了 3 个已知的 `-ffast-math` 差异（msta_rna, all_vs_all, database_search），根因相同——内存布局改变 → 编译器优化决策不同 → 浮点累积分歧。TMalign_main 翻转将这种影响从**坐标数组层面**扩展到了**函数调用层级**，影响范围扩大。

---

## 六、后续方案

### 方案 A：接受差异，更新 baseline

- 翻转后的 Coords& 版本在**数学上等价**（所有运算式相同）
- 差异是编译器代码生成的**确定性行为**（不随机，可复现）
- 更新 baseline 后，回归测试可正常通过
- 代价：baseline 与 master 分支不再逐字节一致

### 方案 B：保持桥接模式（当前）

- `TMalign_main(Coords&)` 桥接 → `TMalign_main(double**)` 真实现
- 所有子函数调用走 double** 重载，数值路径不变
- **14/14 ALL PASS**（去掉 `-ffast-math` 后）
- 代价：存在一层桥接，不是最终 C++ 风格

### 方案 C：修复编译器差异（长期）

- 调查 GCC/Clang 是否有编译选项可以消除 `Coords&` vs `double**` 的指令生成差异
- 或修改 Kabsch SVD 实现为确定性的定点运算
- 或升级到支持 `std::float64_t` 等确定性浮点的 C++23 标准

### 推荐路线

```
当前（桥接模式，14/14 PASS）
  → DP 矩阵容器化（~31 处 NewArray → DPMatrix/PathMat）
  → 非坐标 NewArray 清理（TMave_mat / ut_mat / xcentroids）
  → TMalign_main 翻转（方案 A，接受差异，更新 baseline）
  → 其他核心函数翻转（TMalign_dimer_main / SOIalign_main / flexalign_main）
  → Wave 4 清理（删除零调用者 double** 重载 + NewArray/DeleteArray 模板）
  → USalign-beta → master 合并
```
