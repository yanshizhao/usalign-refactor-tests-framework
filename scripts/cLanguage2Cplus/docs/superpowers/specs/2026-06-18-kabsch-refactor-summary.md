# Kabsch 算法重构：解析法 SVD 替换为循环雅可比迭代

> 记录日期：2026-06-18
> 涉及文件：`USalign/Kabsch.h`
> 关联文档：`jacobi-eigenvalue-decomposition-review.md`
> 背景：USalign C→C++ 重构中，将 `inline bool Kabsch` 函数的特征值分解
>       从解析法（三次方程）替换为循环雅可比迭代法

---

## 一、重构概述

### 1.1 原始方案（解析法）

`master` 分支的 Kabsch 算法使用**三次方程解析解**进行 3×3 对称矩阵的特征值分解：

```
1. 求解三次特征多项式，直接得到三个特征值
   → 特征值天然是降序排列，无需排序
2. 用伴随矩阵(adjugate)方法计算第 0 列和第 2 列的特征向量
3. 第 1 列由叉乘得到: v₁ = v₂ × v₀
   → 自动保证特征向量矩阵行列式为 +1（右手正交系）
```

### 1.2 新方案（循环雅可比迭代）

C++ 重构版本替换为**循环雅可比迭代法**：

```
1. 通过吉文斯旋转变换迭代地对角化矩阵
   → 特征值顺序随机，需要额外排序
2. 三列特征向量都由雅可比方法计算得出
3. 排序时交换列会改变特征向量矩阵的行列式符号
   → 需要额外修正
```

---

## 二、新增/修改的函数

### 2.1 `is_zero_matrix` — 零矩阵检测（新增）

```cpp
// Kabsch.h:55-62
static inline bool is_zero_matrix(const RotMat& M, double epsilon)
{
    double sum = 0.0;
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            sum += std::fabs(M[i][j]);
    return sum <= epsilon;
}
```

**作用**：在 `jacobi_eigen3` 迭代前快速判断零矩阵，避免空跑 10 轮。

### 2.2 `jacobi_rotate_step` — 单步吉文斯旋转（保留）

```cpp
// Kabsch.h:6-51
static inline void jacobi_rotate_step(RotMat& A, RotMat* eig_vecs,
                                      int p, int q, double epsilon);
```

一次吉文斯旋转，消去对称矩阵 `A` 的 `(p,q)` 非对角元，按需同步更新特征向量矩阵。

**关键属性**：吉文斯旋转矩阵的行列式为 +1，因此特征向量矩阵的行列式在迭代过程中保持不变。

### 2.3 `jacobi_eigen3` — 3×3 循环雅可比特征值分解（修改）

```cpp
// Kabsch.h:69-114
inline bool jacobi_eigen3(const RotMat& M,
                          std::array<double, 3>& eig_vals,
                          RotMat* eig_vecs = nullptr,
                          double epsilon = 1e-12,
                          int max_sweeps = 10);
```

**修改内容**：

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 收敛判据 | 绝对阈值 `off_diag < epsilon` | 相对阈值 `off_diag < epsilon × diag_norm` |
| 零矩阵处理 | 无（依赖调用方保护） | `is_zero_matrix` 提前返回 |

退出路径：

```
① is_zero_matrix 检测 → 全零矩阵直接返回（新增）
② off_diag < epsilon × diag_norm → 相对精度达标，提前退出
③ sweep < max_sweeps 不满足 → 跑满 10 轮退出（极少发生）
```

### 2.4 `Kabsch` — 主函数（保留，算法流更新）

```cpp
// Kabsch.h:133
inline bool Kabsch(const CoordArray& x, const CoordArray& y, int n, int mode,
                   double &rms, Vec3& t, RotMat& u);
```

**重构前数据流（`master` 分支 — 解析法）**：

```
输入 x, y (两堆原子坐标)
  ↓
模块1: 初始化与边界校验
  ↓
模块2: 计算质心 xc, yc 和协方差矩阵 r
  ↓
模块3: 计算 det(r) → sigma（用于反射修正）
  ↓
模块4: 计算 Gram 矩阵 M = r^T * r（存储为 rr[6] 压缩格式）
  ↓
模块5: 计算 spur = tr(M)/3, cof, det(M)
  ↓
模块6: 求解三次特征方程（三角函数解析解）
       h = spur² - cof, d = h³ - g²
       θ = atan2(√d, -g) / 3
       cth = √h·cosθ, sth = √h·√3·sinθ
       → 特征值 e = [spur+2cth, spur-cth+sth, spur-cth-sth]
       → 特征值天然降序，无需排序
  ↓
模块7: 用伴随矩阵(adjugate)计算第 0、2 列特征向量
       ss[k] = adj(M - λI) 的 6 个独立元素
       选绝对值最大的行作为基准，提取特征向量
  ↓
模块8: Gram-Schmidt 修正第 0、2 列的正交性
  ↓
模块9: 第 1 列由叉乘得到: a[:,1] = a[:,2] × a[:,0]
       → 自动保证 det(a) = +1（右手正交系）
  ↓
模块10: b = r * a（左奇异向量），Gram-Schmidt 正交化，叉乘第三列
        u = b * a^T（最优旋转矩阵）
  ↓
模块11: t = yc - u * xc（平移向量）
  ↓
模块12: 奇异值修正与残差计算
```

**重构后数据流（`USalign-beta` 分支 — 雅可比迭代法）**：

```
输入 x, y (两堆原子坐标)
  ↓
模块1: 初始化与边界校验
  ↓
模块2: 计算质心 xc, yc 和协方差矩阵 r
  ↓
模块3: 计算 det(r) → sigma（用于反射修正）
  ↓
模块4: M = r^T * r（Gram 矩阵）
  ↓
模块5: jacobi_eigen3(M, e, &a) → 特征值 e, 特征向量 a = V
  ↓
模块6: 特征值降序排序，同步交换 a 的列
  ↓
模块7: 行列式校正（确保 det(a) = +1）
  ↓
模块8: b = r * a（左奇异向量），Gram-Schmidt 正交化，叉乘第三列
        u = b * a^T（最优旋转矩阵）
  ↓
模块9: t = yc - u * xc（平移向量）
  ↓
模块10: 奇异值修正与残差计算
```

---

## 三、重构中发现并修复的核心问题

### 3.1 排序导致的特征向量行列式翻转（已修复）

**详见** `jacobi-eigenvalue-decomposition-review.md` 第四章

**根因**：雅可比输出的特征值顺序随机，排序时交换特征向量矩阵的列导致行列式符号翻转（50% 概率），最终旋转矩阵变为反射矩阵。

**修复**：排序后计算 det(a)，若为负则翻转第三列（对应最小奇异值）。

```cpp
// Kabsch.h 第 226-235 行
double det_a = ...;
if (det_a < 0.0) {
    for (k = 0; k < 3; ++k)
        a[k][2] = -a[k][2];
}
```

### 3.2 绝对阈值收敛判据失效（本次修复）

**根因**：Gram 矩阵元素量级 $10^8 \sim 10^{12}$，要求非对角元降到 $10^{-12}$ 以下需要 $10^{20}$ 倍衰减，远超双精度浮点极限。收敛检查形同虚设，始终靠 `max_sweeps=10` 硬退出。

**修复**：改为相对阈值 `off_diag < epsilon × diag_norm`，等效绝对阈值约 $10^{-4} \sim 10^0$，通常 3~6 轮即可触发收敛退出。

### 3.3 零矩阵空跑 10 轮（本次修复）

**根因**：全零矩阵传入时，相对阈值条件 `0 < 0` 永不触发，空跑 10 轮。

**修复**：新增 `is_zero_matrix` 函数，在循环前快速检测并直接返回。

---

## 四、修改前后对比

### 4.1 函数清单

| 函数 | 修改前 | 修改后 |
|---|---|---|
| `is_zero_matrix` | 不存在 | 新增（零矩阵检测） |
| `jacobi_rotate_step` | 存在 | 保留，未修改 |
| `jacobi_eigen3` | 绝对阈值，无零矩阵保护 | 相对阈值 + is_zero_matrix |
| `Kabsch` | 解析法 SVD | 雅可比迭代法 + 行列式校正 |

### 4.2 收敛特性

| 维度 | 修改前 | 修改后 |
|---|---|---|
| 收敛条件 | `off_diag < 1e-12` | `off_diag < 1e-12 × diag_norm` |
| 等效阈值（对 $10^{10}$ 矩阵） | $10^{-12}$（不可达） | $\approx 3 \times 10^{-2}$（可达） |
| 实际退出方式 | 几乎永远靠 max_sweeps=10 | 通常 3~6 轮提前 break |
| 零矩阵处理 | 空跑 10 轮 | 一次检测直接返回 |

---

## 五、文件位置索引

| 内容 | 文件 | 行号 |
|---|---|---|
| `is_zero_matrix` 函数 | Kabsch.h | 55-62 |
| `jacobi_rotate_step` 单步旋转 | Kabsch.h | 6-51 |
| `jacobi_eigen3` 循环雅可比分解 | Kabsch.h | 69-114 |
| `Kabsch` 主函数 | Kabsch.h | 133-342 |
| 排序（bug 位置） | Kabsch.h | 214-224 |
| 行列式校正（fix） | Kabsch.h | 226-235 |
| Gram 矩阵构造 | Kabsch.h | 195-201 |
| 左奇异向量 + 旋转矩阵 | Kabsch.h | 238-308 |
| 残差计算 | Kabsch.h | 325-340 |

---

## 六、参考资料

1. Kabsch, W. (1976). A solution for the best rotation to relate two sets of vectors. *Acta Cryst.* A32, 922-923.
2. Golub, G. H. & Van Loan, C. F. (2013). *Matrix Computations* (4th ed.). Johns Hopkins University Press.
3. `jacobi-eigenvalue-decomposition-review.md` — 雅可比特征值分解回顾，含排序行列式翻转的完整分析。
