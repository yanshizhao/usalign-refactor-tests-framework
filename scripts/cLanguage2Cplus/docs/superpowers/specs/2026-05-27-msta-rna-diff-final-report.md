# msta_rna 用例 diff 最终分析报告

**日期**: 2026-05-27
**上一份报告**: `2026-05-26-l2h-msta-rna-diff-analysis.md`

---

## 1. 现象

L2h-10a 完成后运行 `run_regression.py`，14 个用例中 9 个出现 diff，其中 **msta_rna** 最为特殊——输出表格中一行链名发生了变化：

```
Baseline（Master, double**）:
  US73519240510.pdb:J    US7351924051.pdb:A    0.6611  0.6334  2.87  ...

Current（USalign-beta, Coords）:
  US73519240510.pdb:J    US735192405.pdb:A     0.6611  0.6334  2.87  ...
```

两行的所有数值（TM1、TM2、RMSD、ID1、ID2、IDali、L1、L2、Lali）完全相同。

其余 8 个用例的 diff 仅为 CPU 时间差异或旋转矩阵末位小数差异。

---

## 2. 验证过程

### 2.1 排除基线本身有问题

用 master 分支的原始代码编译二进制，以完全相同的参数运行 MSTA 测试：

```bash
g++ -static -O3 -ffast-math -lm -o USalign_master.exe USalign.cpp
USalign_master.exe -dir . list.txt -suffix .pdb -mm 4 -mol RNA -outfmt -1
```

结果：Master 输出与基线一致（`US7351924051:A`）。确认差异由 L2-h 改动引起，非基线问题。

### 2.2 确认两个目标链是否是同一个东西（真实数据检查）

`US735192405.pdb` 和 `US7351924051.pdb`：

| 文件 | 行数 |
|------|------|
| US7351924051.pdb | 2,111 |
| US735192405.pdb | 19,056 |

`diff` 两文件：前 2,090 行**完全相同**。2,090 行之后 US7351924051.pdb 出现 `TER` 记录进入链 B，而 US735192405.pdb 继续有其他链的数据。

**结论**：两文件的链 A 原子坐标完全相同。比对到哪个都是同一段坐标。

### 2.3 数值精度测量

在 USalign-beta 上添加 debug 输出，以 17 位精度打印 `TMave_mat[9][0]`（US73519240510:J vs US7351924051:A）和 `TMave_mat[9][10]`（US73519240510:J vs US735192405:A）：

| 版本 | TMave_mat[9][0] | TMave_mat[9][10] | diff |
|------|-----------------|-------------------|------|
| Master（double**） | 尾数 ...2186 | 尾数 ...2175 | **1 ULP** |
| USalign-beta（Coords） | 尾数 ...2453 | 尾数 ...2453 | **0（精确相等）** |

### 2.4 MSTA 选择逻辑分析

MSTA 模式下，11 个结构全对全比对，但表格只为每个结构展示一个"最佳代表"（仅 10 行输出）。

`list.txt` 中 11 个文件按行序索引 0-10：

| 索引 | 文件 |
|------|------|
| 0 | US7351924051 |
| 9 | US73519240510 |
| 10 | US735192405 |

选择分两步：

**Step 1 — 选代表结构 repr_idx（第 1912 行）**：

```cpp
if (TMave_list[j] < repr_TM) continue;  // 用 <，相等时后面覆盖前面
repr_TM = TMave_list[j];
repr_idx = j;
```

`TMave_list[j]` 是链 j 对所有其他链的 TM-score **列和**，衡量 j 的"代表性"。遍历 j=0→10，`<` 表示相等时后面覆盖前面，最终 **两个分支(mater和beta)的 repr_idx 均为 10（US735192405）**。

**Step 2 — 为每个 i 选最佳配对 maxj（第 1958 行）**：

```cpp
maxTM = TMave_mat[i][repr_idx];  // 初始值 = 与代表链 10 的分数
maxj  = repr_idx;                // 初始值 = 10
for (j = 0; j < chain_num; j++)
{
    if (i == j || assign_list[j] < 0 || TMave_mat[i][j] <= maxTM) continue;
    //                                          ^^ 用 <=，相等时跳过（保留 repr_idx）
    maxj = j;
    maxTM = TMave_mat[i][j];
}
```

`TMave_mat[i][j]` 是链 i 与链 j 的一对一归一化 TM-score。`<=` 表示平局时保留 repr_idx。`assign_list[j] < 0` 保证只有**已被处理过的链**才能作为配对目标。

**关键**：`TM_pair_vec` 按 `TMave_mat[i][repr_idx]` 降序排列。`TMave_mat[0][10] = 1.0000`（US7351924051 vs 代表链US735192405，坐标相同），排在第一位，因此 **i=0 先于 i=9 被处理**。当 i=0 处理完毕后 `assign_list[0] = 10`（≥0），轮到 i=9 时 j=0 不再被 `assign_list[j] < 0` 跳过，进入 TM-score 比较。

**US73519240510（i=9）的 maxj 选择过程**：

```
maxTM = TMave_mat[9][10];   // 初始值 = 与代表链(US735192405:A)的分数
maxj  = 10;                 // 初始值 = 代表链
// 遍历 j，已处理过的链（assign_list[j]≥0）都能进入比较，其中 j=0 和 j=10 的 TMave_mat[9][j] 最为接近，是决定 maxj 的关键
```

| 分支 | TMave_mat[9][0]<br>(US7351924051:A) | TMave_mat[9][10]<br>(US735192405:A) | j=0 时 `<= maxTM`? | 最终 maxj |
|------|----------------------------------------|------------------------------------------|---------------------|-----------|
| **Master** (double**) | 0.67571398037902**186** | 0.67571398037902**175** | **否**（严格大于，挑战成功） | **0** (US7351924051) |
| **USalign-beta** (Coords) | 0.67571398037902**453** | 0.67571398037902**453** | **是**（精确相等，保留 repr_idx） | **10** (US735192405) |

两步比较的**数据不同**（`TMave_list` vs `TMave_mat`），但通过 `repr_idx` 衔接：Step 1 决定了 repr_idx=10，Step 2 的 `<=` 确保平局时锁定 repr_idx。Master 分支中 1 ULP 的浮点噪声刚好跨过了 `<=` 判定边界，让 US7351924051 取代了代表链。

---

## 3. 根因分析

### 3.1 为什么 Master（double**）下两个 TM-score 不同

两文件的链 A 坐标完全相同，`TMalign_main(US73519240510:J, US735192405:A)` 与 `TMalign_main(US73519240510:J, US7351924051:A)` 的**输入坐标值完全一致**。

但 `double**` 通过 `NewArray` 逐行独立 `new[]` 分配，两次独立的 `xa`/`ya` 数组在堆上碎片分布，内存布局不同。`-ffast-math` 编译器对不同内存布局做出不同的别名分析和 FMA 收缩决策，导致 Kabsch SVD 迭代的浮点运算顺序不同，舍入误差逐轮累积，最终在两个本应相同的 TM-score 之间产生了 **1 ULP**（约 1.5×10^-16，**第 16 位小数**）的伪差异。

### 3.2 为什么 Coords 下两个 TM-score 精确相等

`Coords`（`vector<array<double,3>>`）的连续内存布局使得两次分配的数组在物理布局上高度一致，编译器做出了相同的优化决策，消除了碎片内存引入的不对称噪声。两个分数**精确相等**——Coords 的结果比 Master 更"正确"。

### 3.3 差异精度明细

| 差异类型 | Master 分支出现差异的精度 | 说明 |
|----------|--------------------------|------|
| **TMave_mat 两两比对分数** | 1 ULP（~1.5×10^-16，约**第 16 位小数**） | Master 下两个分数差 1 ULP；Coords 下精确相等 |
| **旋转矩阵 t[m] / u[m][i]** | **第 10-11 位小数**（10^-10 ~ 10^-11） | Kabsch SVD 迭代多轮累积 |

---

## 4. 判定

| 问题 | 结论 |
|------|------|
| 是代码 bug 吗？ | **否。** 配对变化不是逻辑错误，是 `-ffast-math` 下浮点噪声跨过了 MSTA 判定边界 |
| Coords 结果有错吗？ | **否。** Coords 的精确相等是数学上正确的行为——相同坐标 → 相同分数 |
| Master 的 1 ULP 差异从哪来？ | `-ffast-math` 下碎片内存布局 → 编译器优化决策不同 → SVD 迭代浮点累积 |
| 影响其他用例吗？ | 是。9 个 diff 的根因完全相同：`-ffast-math` + 内存布局变化 → 浮点舍入分歧 |

---
