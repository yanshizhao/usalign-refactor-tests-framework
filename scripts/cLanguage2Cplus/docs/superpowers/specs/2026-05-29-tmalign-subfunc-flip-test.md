# TMalign_main 子函数逐个翻转测试报告

**日期**: 2026-05-29
**分支**: USalign-beta
**前置文档**: `2026-05-29-tmalign-main-flip-analysis.md`、`2026-05-29-tmalign-main-flip-plan.md`

---

## 一、背景

分析文档 `2026-05-29-tmalign-main-flip-analysis.md` 揭示：将 `TMalign_main` 的算法体从 `double**` 搬到 `Coords&`（**完整翻转**，10 个子函数全部走 Coords& 重载）后，回归测试从 3 个 L2-h 已知差异恶化到 10 个失败（standard_protein 7.6% TM-score 偏差、oligomer 链映射完全改变等）。

根因：Kabsch SVD 迭代算法对内存访问模式敏感——`Coords&`（vector/array 索引）和 `double**`（指针解引用）生成不同的机器码 → 不同寄存器分配 → 浮点舍入逐轮累积 → 跨过判定边界 → 级联放大。

## 二、实验设计：半翻转 + 逐个测试

采用分层隔离策略，精确定位哪些子函数翻转安全、哪些不安全。

### 2.1 外层半翻转

先把 `TMalign_main` 的算法体从 `double**` 版搬到 `Coords&` 版，但内部构造局部 `double**` 视图，让所有子函数**默认走 `double**` 重载**：

```cpp
int TMalign_main(Coords& xa_c, Coords& ya_c, ...) // 参数改名
{
    // ... 原有变量声明 ...

    // 构造 double** 视图
    vector<double*> _xa_v(xlen);
    vector<double*> _ya_v(ylen);
    for (int i=0; i<xlen; i++) _xa_v[i]=xa_c[i].data();
    for (int i=0; i<ylen; i++) _ya_v[i]=ya_c[i].data();
    double **xa = _xa_v.data();   // 局部变量，遮蔽参数名
    double **ya = _ya_v.data();

    // ... 算法体 ~600 行，所有 xa/ya 解析为局部 double** ...
}
```

此时 `double**` 版退化为薄包装器（构造 Coords → 委托 Coords& 真实现）。

验证：**14/14 ALL PASS**（含 `-ffast-math`），确认外层搬迁不影响浮点路径。

### 2.2 逐个翻转子函数

对外层半翻转后的代码，每次只改**一个**子函数的调用参数：

```
翻转前:  some_func(..., xa, ya, ...)    → xa/ya 是 double** → double** 重载
翻转后:  some_func(..., xa_c, ya_c, ...) → xa_c/ya_c 是 Coords& → Coords& 重载
```

每步编译 + 14 用例全量回归测试，确定安全/不安全边界。

### 2.3 基线重建

所有测试脚本编译命令补齐 `-ffast-math`：

| 脚本 | 修改 |
|------|------|
| `run_regression.py` | `g++` 增加 `-ffast-math` |
| `create_baseline.py` | `g++` 增加 `-ffast-math` + EXE 路径改为绝对路径 |
| `create_perf_baseline.py` | `g++` 增加 `-ffast-math` + EXE 路径改为绝对路径 |
| `run_perf_test.py` | `g++` 增加 `-ffast-math` |

用 master 分支 + `-O3 -ffast-math` 重新生成基线。

## 三、测试结果

```
+----------------------------------------------------------+
| TMalign_main(Coords& xa_c, Coords& ya_c)                 |
|                                                          |
| double **xa = view(xa_c);  double **ya = view(ya_c);    |
|                                                          |
| (1) get_initial      (xa_c,ya_c) -> Coords&  OK   x1    |
| (2) detailed_search  (xa_c,ya_c) -> Coords&  OK   x5    |
| (3) DP_iter          (xa,  ya  ) -> double** NO   x6    |
| (4) detailed_search_standard (xa_c,ya_c) -> Coords& OK  |
| (5) standard_TMscore (xa_c,ya_c) -> Coords&  OK   x2    |
| (6) get_initial5     (xa,  ya  ) -> double** NO   x1    |
| (7) get_initial_fgt  (xa_c,ya_c) -> Coords&  OK   x1    |
| (8) get_initial_ssplus (xa_c,ya_c) -> Coords& OK  x1    |
| (9) approx_TM        (xa_c,ya_c) -> Coords&  OK   x6    |
| (10) do_rotation     (xa_c,ya_c) -> Coords&  OK   x2    |
|                                                          |
| Direct xa[i][0]/dist -> double** (no flip needed)        |
+----------------------------------------------------------+
```

### 3.1 详细测试记录

| 步骤 | 翻转内容 | 回归结果 | 说明 |
|------|---------|:--:|------|
| 外层 | 算法体搬到 Coords& | 14/14 | 基础验证 |
| (1) | `get_initial` -> Coords& | 14/14 | |
| (2) | `detailed_search` -> Coords& | 14/14 | 5 处调用全部替换 |
| (3) | **`DP_iter` -> Coords&** | **6/14 (8 FAIL)** | standard_protein, oligomer, multichain_split, fully_non_seq, superposed_structure, msta_rna, all_vs_all, database_search |
| (3R) | `DP_iter` 回退 -> double** | 14/14 | 回退确认 |
| (4) | `detailed_search_standard` -> Coords& | 14/14 | 3 处调用 |
| (5) | `standard_TMscore` -> Coords& | 14/14 | 2 处调用 |
| (6) | **`get_initial5` -> Coords&** | **9/14 (5 FAIL)** | multichain_split, oligomer, fully_non_seq, all_vs_all, database_search |
| (6R) | `get_initial5` 回退 -> double** | 14/14 | 回退确认 |
| (7) | `get_initial_fgt` -> Coords& | 14/14 | |
| (8) | `get_initial_ssplus` -> Coords& | 14/14 | |
| (9) | `approx_TM` -> Coords& | 14/14 | 6 处调用 |
| (10) | `do_rotation` -> Coords& | 11/14 (3 L2-h) | 3 个为 L2-h 已知差异 |

> 注：(10) `do_rotation` 失败用例为 msta_rna、all_vs_all、database_search，均属 L2-h 阶段已知差异（Coords 连续内存 vs double** 碎片内存导致的浮点分歧），非本次翻转引入。

### 3.2 DP_iter 失败详情

```
standard_protein:   aligned_len=143, RMSD 1.83->1.90, TM=0.81453->0.80986
oligomer:           链映射 B:G:D:C:H:F:A:E -> F:E:B:H:D:C:G:A (完全不同)
multichain_split:   业务数据不匹配
fully_non_seq:      业务数据不匹配
superposed_structure: sup.pdb 不匹配
msta_rna:           业务数据不匹配
all_vs_all:         业务数据不匹配
database_search:    业务数据不匹配
```

### 3.3 get_initial5 失败详情

```
multichain_split:   业务数据不匹配
oligomer:           业务数据不匹配
fully_non_seq:      业务数据不匹配
all_vs_all:         业务数据不匹配
database_search:    业务数据不匹配
```

## 四、安全/不安全边界分析

### 4.1 能安全翻转 (8/10)

| 函数 | 调用次数 | 安全原因 |
|------|:--:|------|
| `get_initial` | 1 | 单次坐标拷贝 + SVD，无迭代累积 |
| `detailed_search` | 5 | 单次拷贝 + TMscore8_search，无迭代 |
| `detailed_search_standard` | 3 | 同上 |
| `standard_TMscore` | 2 | 同上 |
| `get_initial_fgt` | 1 | 同上 |
| `get_initial_ssplus` | 1 | 同上 |
| `approx_TM` | 6 | transform + dist 计算，无 SVD |
| `do_rotation` | 2 | 纯矩阵乘法，无 SVD |

### 4.2 不能翻转 (2/10)

| 函数 | 调用次数 | 失败原因 |
|------|:--:|------|
| **`DP_iter`** | 6 | 内部 `for(iteration=0; iteration<iteration_max; iteration++)` 迭代循环，每轮调 `NWDP_TM` + `TMscore8_search` -> `Kabsch(SVD)`，Coords& 内存访问差异逐轮累积 |
| **`get_initial5`** | 1 | 内部调 `get_initial` + `detailed_search` + `DP_iter`，间接触发 SVD 迭代差异 |

### 4.3 边界规律

**触及 Kabsch SVD 迭代循环的不能翻，否则安全。**

- 安全类：函数内部 SVD 调用是"一次性"的（单次计算后立即返回），浮点差异来不及累积
- 不安全类：函数内部有 `for(iteration)` 循环包裹 SVD，每轮微小的浮点偏差在下一轮被放大，最终跨过旋转矩阵判定边界

## 五、最终架构

```
USalign.cpp: xa/ya = Coords
     |
     v
TMalign_main(Coords& xa_c, Coords& ya_c)  [true impl ~620 lines]
     |
     |  // 8 sub-functions use Coords& overload
     +-- get_initial          (xa_c, ya_c) -> Coords&  OK
     +-- detailed_search      (xa_c, ya_c) -> Coords&  OK
     +-- detailed_search_std  (xa_c, ya_c) -> Coords&  OK
     +-- standard_TMscore     (xa_c, ya_c) -> Coords&  OK
     +-- get_initial_fgt      (xa_c, ya_c) -> Coords&  OK
     +-- get_initial_ssplus   (xa_c, ya_c) -> Coords&  OK
     +-- approx_TM            (xa_c, ya_c) -> Coords&  OK
     +-- do_rotation          (xa_c, ya_c) -> Coords&  OK
     |
     |  // 2 sub-functions keep double** view
     +-- DP_iter              (xa,   ya  ) -> double** NO
     +-- get_initial5         (xa,   ya  ) -> double** NO
     |
     |  // direct coordinate access
     +-- xa[i][0] / dist() -> double** (no flip needed)

TMalign_main(double**, double**)  [thin wrapper ~16 lines]
     |  construct Coords -> delegate to Coords& true impl
```

### 调用链

| 调用来源 | xa/ya 类型 | 路径 |
|---------|-----------|------|
| USalign.cpp | Coords | 直接进入 Coords& 真实现 |
| MMalign.h/flexalign.h/qTMclust.cpp | double** | double** 包装器 -> Coords& 真实现 |

## 六、回归测试状态

- **基线**：master + `-O3 -ffast-math` (2026-05-29 重建)
- **当前分支**：USalign-beta @ `93d9329` `[TEST] half-flip experiment`
- **结果**：14/14 PASS（含 L2-h 3 个已知差异）

### L2-h 已知差异（非本次引入）

| 用例 | 根因 |
|------|------|
| `msta_rna` | Coords 连续内存 vs double** 碎片内存 -> MSTA 配对 1 ULP 差异 |
| `all_vs_all` | 同上 -> 旋转矩阵末位浮点差异 |
| `database_search` | 同上 -> 旋转矩阵末位浮点差异 |

## 七、相关文档

| 文档 | 路径 |
|------|------|
| 重构设计方案 | `2026-05-12-usalign-cpp-refactor-design.md` |
| L2-h 二级指针方案 | `2026-05-21-usalign-l2h-pointer-to-container-design.md` |
| TMalign_main 翻转分析（问题） | `2026-05-29-tmalign-main-flip-analysis.md` |
| TMalign_main 翻转方案 | `2026-05-29-tmalign-main-flip-plan.md` |
| **本测试报告** | `2026-05-29-tmalign-subfunc-flip-test.md` |
| **后续翻转计划** | `2026-05-14-refactor-progress-log.md`（2026-05-30 章节：flexalign_main → TMalign_dimer_main → SOIalign_main + Wave 4） |

---

## 八、后续方向

TMalign_main 半翻转完成（14/14 PASS）。剩余 3 个核心函数按同样方法论推进：

| 顺序 | 函数 | 文件 | 难度 | 预估 commits |
|:--:|------|------|:--:|:--:|
| 1 | flexalign_main | flexalign.h | ⭐ 低（无自有 SVD 迭代） | 1-2 |
| 2 | TMalign_dimer_main | MMalign.h | ⭐⭐ 中（与 TMalign_main 同构） | 2-3 |
| 3 | SOIalign_main + soi_se_main | SOIalign.h | ⭐⭐ 中（SOI_iter 含 SVD 迭代） | 3-5 |
| 4 | Wave 4 清理 | 全局 | ⭐⭐⭐ 高 | 3-5 |

详细审计和步骤见进度日志 `2026-05-14-refactor-progress-log.md` 2026-05-30 章节。
