# TMalign_main 方向翻转 — 详细执行方案

**日期**: 2026-05-29
**前置文档**: `2026-05-21-usalign-l2h-pointer-to-container-design.md`（第 12.9 节）
**当前分支**: USalign-beta（HEAD `d78e199`，领先 master 101 commits）
**当前阶段**: Phase 11 Wave 3 — 核心函数方向翻转

---

## 一、当前状态

```
TMalign_main(double**, double**, ...) 行 4906-5521  ≈615行  真实现 (xa/ya=double**)
TMalign_main(Coords&, double**, ...)  行 5524-5550  ≈27行   混合桥接 (CPalign用)
TMalign_main(Coords&, Coords&, ...)   行 5782-5811  ≈30行   桥接 (构造double**视图→委托)
```

## 二、目标状态

```
TMalign_main(Coords&, Coords&, ...)  行 5782+      ≈615行  真实现 (xa/ya=Coords&)
TMalign_main(double**, double**, ...) 行 4906+      ≈25行   薄包装器 (构造Coords→委托)
TMalign_main(Coords&, double**, ...)  行 5524+      ≈25行   直接委托Coords&真实现
```

---

## 三、前提条件审计

TMalign_main 算法体中 `xa`/`ya` 的子函数调用——Coords& 重载覆盖情况：

| 子函数 | 是否有 const Coords& x/y 重载 | P11 来源 | 说明 |
|--------|:--:|:--:|------|
| `get_initial(x, y)` | ✅ | P11-6 | 行 1348+ |
| `detailed_search(x, y)` | ✅ | P11-1 | 行 866+ |
| `detailed_search_standard(x, y)` | ✅ | P11-1 | — |
| `DP_iter(x, y)` | ✅ 两种 | P11-9 | double** DP / DPMatrix DP 各一 |
| `get_initial5(x, y)` | ✅ | P11-8 | 行 2953+ |
| `get_initial_fgt(x, y)` | ✅ | P11-7 | — |
| `standard_TMscore(x, y)` | ✅ | P11-2 | 行 4777 `const Coords& x/y` |
| `get_initial_ss(x)` | ✅ 不传xa/ya | — | 只传 secx/secy |
| `do_rotation(xa, xt)` | ✅ | L2h-03 | basic_fun.h:872 `Coords&, Coords&` |
| `xa[i][j]` 直接访问 | ✅ 语法等价 | — | 行 5344-5350 纯读取 |
| `get_initial_ssplus(..., x, y)` | **❌ 缺失** | — | 现有 Coords& 版(行2256) x/y 仍是 double** |
| `approx_TM(xa, ya)` | **❌ 缺失** | — | 只有 double** 版(行4829) |

**需要新增 2 个重载**（步骤 1-2），然后执行翻转（步骤 3-6）。

---

## 四、关键代码审查发现

### 4.1 `#endif`（行 5551）分割编译区域

```
行 4906-5521: TMalign_main(double**, double**, ...)  ← 在 #ifndef TMalign_h 守卫内
行 5524-5550: TMalign_main(Coords&, double**, ...)   ← 在守卫内
行 5551:      #endif                                   ← 守卫结束
行 5782-5811: TMalign_main(Coords&, Coords&, ...)    ← 在守卫外
```

翻转后：double** 包装器留在守卫内（行 4906），Coords& 真实现留在守卫外（行 5782）。`#pragma once` 确保单次包含，功能不受影响。

### 4.2 `xa`/`ya` 应保持 `Coords&`（非 const）

| 场景 | `Coords&`（非 const） | `const Coords&` |
|------|:--:|:--:|
| `do_rotation(xa, xt, ...)` 行 5330/5448 | ✅ 匹配 `do_rotation(Coords&, Coords&, ...)` basic_fun.h:872 | ❌ `const Coords&` 不能传 `Coords&` 参数 |
| `&ya[j][0]` 行 5338/5479 | ✅ `double*`（匹配 `dist(double*, double*)`） | ⚠️ `const double*` 需 const_cast |
| 传递给子函数 | ✅ 自动隐式转 `const Coords&` | ✅ 直接匹配 |

**结论**: 翻转后签名保持 `Coords& xa, Coords& ya`（与当前桥接一致）。

### 4.3 `dist` 和 `do_rotation` 在非 const Coords& 下的类型推导

```cpp
// 算法体中所有 xa/ya 直接使用（行 5330-5513）
do_rotation(xa, xt, xlen, t, u);                    // xa=Coords& → 行 basic_fun.h:872
d=sqrt(dist(&xt[i][0], &ya[j][0]));                  // ya=Coords& → &ya[j][0]=double*
d=sqrt(dist(&xt[m1[k]][0], &ya[m2[k]][0]));          // 同上
xtm[k][0]=xa[i][0]; xtm[k][1]=xa[i][1]; xtm[k][2]=xa[i][2];  // xa[i]=array<double,3>&
ytm[k][0]=ya[j][0]; ytm[k][1]=ya[j][1]; ytm[k][2]=ya[j][2];  // ya[j]=array<double,3>&
```

所有操作在 `Coords&` 下与 `double**` 语法完全等价，**零改动**。

### 4.4 `approx_TM` const_cast 需求

当 xa 是 `const Coords&` 时（新重载的参数）：
```cpp
transform(t, u, &xa[i][0], &xtmp[0]);  // &xa[i][0] = const double*
// transform 签名: void transform(double t[3], double u[3][3], double *x, double *x1)
// const double* 不能隐式转 double* → 编译错误
```

需要 const_cast（此模式已在 `score_matrix_rmsd_sec` 行 2195 验证安全）：
```cpp
transform(t, u, (double*)&xa[i][0], &xtmp[0]);
d = sqrt(dist((double*)&xtmp[0], (double*)&ya[j][0]));
```

### 4.5 步骤 3→4 的算法体文本重复问题（关键）

步骤 3 将算法体（~600 行）复制到 Coords& 桥接位置后，同一段文本在文件中出现两次。步骤 4 再用该文本做 `old_string` 替换 double** 版时，Edit tool 会因为 `old_string` 不唯一而直接 FAIL。

**解决方案**：步骤 3 插入算法体时，在开头附加一行唯一标记注释：

```cpp
{
    double D0_MIN;        //for d0
    double Lnorm;         //normalization length
// [Coords& true implementation]
    double score_d8,d0,d0_search,dcu0;//for TMscore search
    ...
}
```

这样两个副本变为可区分。步骤 4 的 `old_string`（不带标记的原版）唯一匹配 double** 函数体。

### 4.6 混合桥接的调用链优化

当前混合桥接（行 5524）：
```
TMalign_main(Coords&, double**, ...)  →  TMalign_main(double**, double**, ...)  [原真实现]
```

翻转后如果不变：
```
TMalign_main(Coords&, double**, ...)  →  TMalign_main(double**, double**, ...)  [包装器]
  → 构造Coords xa_tmp (从double**拷贝)  →  TMalign_main(Coords&, Coords&, ...)  [真实现]
```

xa 已为 Coords，经过 `xa_view.data()` → double** → 被包装器再拷贝回 Coords（双重拷贝）。应改为直接委托 Coords& 真实现：

```
TMalign_main(Coords&, double**, ...)  →  构造 Coords ya_tmp (从double** ya一次拷贝)
  →  TMalign_main(Coords&, Coords&, ...)  [真实现]
```

---

## 五、原子化执行步骤（6 步）

### 步骤 1：新增 `approx_TM(const Coords&, const Coords&)` 重载

| 项目 | 内容 |
|------|------|
| 文件 | `TMalign.h` |
| 插入位置 | 在行 4860（原 `approx_TM` 函数结束）之后 |
| 改动量 | ~30 行新函数 |
| 风险 | **零** — 新增重载，零调用者，零波及 |

操作：复制现有 `approx_TM` 函数体，签名改为：

```cpp
double approx_TM(const int xlen, const int ylen, const int a_opt,
    const Coords& xa, const Coords& ya, double t[3], double u[3][3],
    const int invmap0[], const int mol_type)
```

Body 中两处加 const_cast：
```cpp
transform(t, u, (double*)&xa[i][0], &xtmp[0]);   // 行 4852
d=sqrt(dist((double*)&xtmp[0], (double*)&ya[j][0])); // 行 4853
```

**验证**: `g++ -O3 -ffast-math -lm -static -o USalign.exe USalign.cpp` → 编译通过。

---

### 步骤 2：新增 `get_initial_ssplus(..., const Coords& x, const Coords& y)` 重载

| 项目 | 内容 |
|------|------|
| 文件 | `TMalign.h` |
| 插入位置 | 在行 2266（现有 Coords& 重载结束）之后 |
| 改动量 | ~20 行新函数 |
| 风险 | **零** — 新增重载，零调用者，零波及 |

操作：复制现有 Coords& 重载（行 2256-2266），改 `double **x, double **y` → `const Coords& x, const Coords& y`：

```cpp
void get_initial_ssplus(Coords& r1, Coords& r2, double **score, bool **path,
    double **val, const char *secx, const char *secy, const Coords& x, const Coords& y,
    int xlen, int ylen, int *y2x0, int *y2x, const double D0_MIN, double d0)
{
    score_matrix_rmsd_sec(r1, r2, score, secx, secy, x, y, xlen, ylen,
        y2x0, D0_MIN,d0);     // 自动匹配 P11-3 Coords& 重载 (行 2175)
    double gap_open=-1.0;
    NWDP_TM(score, path, val, xlen, ylen, gap_open, y2x);
}
```

**验证**: 编译通过。

---

### 步骤 3：Coords& 桥接 → 真实现（带标记的算法体搬迁）

| 项目 | 内容 |
|------|------|
| 文件 | `TMalign.h` |
| 修改位置 | 行 5797-5811（桥接体 14 行）→ 替换为算法体 + 标记 |
| 改动量 | 14 行 → ~602 行 |
| 风险 | **中** — 精确匹配旧桥接体文本 |

**old_string**（当前桥接体，精确文本）：

```cpp
{
    vector<double*> xa_view(xlen);
    vector<double*> ya_view(ylen);
    for (int i=0; i<xlen; i++) xa_view[i]=xa[i].data();
    for (int i=0; i<ylen; i++) ya_view[i]=ya[i].data();
    return TMalign_main(xa_view.data(), ya_view.data(),
        seqx, seqy, secx, secy,
        t0, u0, TM1, TM2, TM3, TM4, TM5,
        d0_0, TM_0, d0A, d0B, d0u, d0a, d0_out,
        seqM, seqxA, seqyA, do_vec,
        rmsd0, L_ali, Liden, TM_ali, rmsd_ali, n_ali, n_ali8,
        xlen, ylen, sequence, Lnorm_ass,
        d0_scale, i_opt, a_opt, u_opt, d_opt, fast_opt,
        mol_type, TMcut);
}
```

**new_string**：从行 4920-5520 复制的算法体全文，在 `double score_d8,` 行之前插入标记注释：

```cpp
{
    double D0_MIN;        //for d0
    double Lnorm;         //normalization length
// [Coords& true implementation]
    double score_d8,d0,d0_search,dcu0;//for TMscore search
    double t[3], u[3][3]; //Kabsch translation vector and rotation matrix
    ...
    return 0; // zero for no exception
}
```

> **关键**：`// [Coords& true implementation]` 标记使此副本与 double** 版的原算法体文本区分开。标记是纯注释，零语义影响。

**验证**: 编译通过。

---

### 步骤 4：double** 真实现 → 薄包装器

| 项目 | 内容 |
|------|------|
| 文件 | `TMalign.h` |
| 修改位置 | 行 4906-5521（double** 函数签名 + 体） |
| 改动量 | ~615 行 → ~25 行（包装器） |
| 风险 | **中** — 需精确匹配原始文本 |

**old_string**：从 `int TMalign_main(double **xa, double **ya,` 到 `return 0; // zero for no exception\n}` 的完整函数。此时文件中该文本**唯一**（步骤 3 的副本有 `// [Coords& true implementation]` 标记）。

**new_string**：

```cpp
// Wrapper — delegates to Coords& true implementation
int TMalign_main(double **xa, double **ya,
    const std::string &seqx, const std::string &seqy, const std::string &secx, const std::string &secy,
    double t0[3], double u0[3][3],
    double &TM1, double &TM2, double &TM3, double &TM4, double &TM5,
    double &d0_0, double &TM_0,
    double &d0A, double &d0B, double &d0u, double &d0a, double &d0_out,
    string &seqM, string &seqxA, string &seqyA, vector<double>&do_vec,
    double &rmsd0, int &L_ali, double &Liden,
    double &TM_ali, double &rmsd_ali, int &n_ali, int &n_ali8,
    const int xlen, const int ylen,
    const vector<string> sequence, const double Lnorm_ass,
    const double d0_scale, const int i_opt, const int a_opt,
    const bool u_opt, const bool d_opt, const bool fast_opt,
    const int mol_type, const double TMcut=-1)
{
    Coords xa_tmp; xa_tmp.reserve(xlen);
    for (int i=0; i<xlen; i++) xa_tmp.push_back({xa[i][0], xa[i][1], xa[i][2]});
    Coords ya_tmp; ya_tmp.reserve(ylen);
    for (int i=0; i<ylen; i++) ya_tmp.push_back({ya[i][0], ya[i][1], ya[i][2]});
    return TMalign_main(xa_tmp, ya_tmp,
        seqx, seqy, secx, secy,
        t0, u0, TM1, TM2, TM3, TM4, TM5,
        d0_0, TM_0, d0A, d0B, d0u, d0a, d0_out,
        seqM, seqxA, seqyA, do_vec,
        rmsd0, L_ali, Liden, TM_ali, rmsd_ali, n_ali, n_ali8,
        xlen, ylen, sequence, Lnorm_ass,
        d0_scale, i_opt, a_opt, u_opt, d_opt, fast_opt,
        mol_type, TMcut);
}
```

**验证**: 编译通过。

---

### 步骤 5：更新混合桥接 `TMalign_main(Coords&, double**, ...)`

| 项目 | 内容 |
|------|------|
| 文件 | `TMalign.h` |
| 修改位置 | 行 5538-5549（混合桥接体） |
| 改动量 | ~12 行 → ~12 行 |
| 风险 | **低** |

**old_string**（当前混合桥接体）：

```cpp
{
    vector<double*> xa_view(xlen);
    for (int i=0; i<xlen; i++) xa_view[i]=(double*)xa[i].data();
    return TMalign_main(xa_view.data(), ya,
        seqx, seqy, secx, secy,
        t0, u0, TM1, TM2, TM3, TM4, TM5,
        d0_0, TM_0, d0A, d0B, d0u, d0a, d0_out,
        seqM, seqxA, seqyA, do_vec,
        rmsd0, L_ali, Liden, TM_ali, rmsd_ali, n_ali, n_ali8,
        xlen, ylen, sequence, Lnorm_ass,
        d0_scale, i_opt, a_opt, u_opt, d_opt, fast_opt,
        mol_type, TMcut);
}
```

**new_string**：直接构造 Coords ya_tmp，委托 Coords& 真实现：

```cpp
{
    Coords ya_tmp; ya_tmp.reserve(ylen);
    for (int i=0; i<ylen; i++) ya_tmp.push_back({ya[i][0], ya[i][1], ya[i][2]});
    return TMalign_main(xa, ya_tmp,
        seqx, seqy, secx, secy,
        t0, u0, TM1, TM2, TM3, TM4, TM5,
        d0_0, TM_0, d0A, d0B, d0u, d0a, d0_out,
        seqM, seqxA, seqyA, do_vec,
        rmsd0, L_ali, Liden, TM_ali, rmsd_ali, n_ali, n_ali8,
        xlen, ylen, sequence, Lnorm_ass,
        d0_scale, i_opt, a_opt, u_opt, d_opt, fast_opt,
        mol_type, TMcut);
}
```

**验证**: 编译通过。

---

### 步骤 6：编译 + 回归测试

```bash
# 1. 编译
cd /d/qlab/us-align_modify/USalign
g++ -O3 -ffast-math -lm -static -o USalign.exe USalign.cpp

# 2. 功能回归
cd /d/qlab/us-align_modify/usalign-refactor-tests-framework/scripts/cLanguage2Cplus
python run_regression.py

# 3. 额外: CPalign 路径测试
cd /d/qlab/us-align_modify/USalign
./USalign.exe 1ajk.pdb 1evv.pdb -ter 2 -cp 1 -outfmt -1
./USalign.exe data/help/model.pdb data/help/native.pdb -cp 1 -outfmt -1
```

**预期**: 14/14 无崩溃，回归测试与基线一致（除去 3 个已知 -ffast-math 浮点差异）。

---

## 六、风险控制

| 风险 | 场景 | 缓解措施 |
|------|------|---------|
| **步骤 3 匹配失败** | 桥接体文本与文件中实际文本有空白差异 | 先用 Read 确认行 5797-5811 精确文本，再执行 Edit |
| **步骤 4 文本仍重复** | `// [Coords& true implementation]` 标记未正确插入 | 若步骤 4 报 not unique，回退步骤 3 检查标记 |
| **编译错误** | 遗漏某个依赖 Coords& 重载的子函数 | 查看编译器错误，补充缺失重载 |
| **CPalign 路径损坏** | 混合桥接委托目标错误 | 用 `-cp 1` 测试验证 |
| **性能退化** | Coords 真实现比 double** 慢 | 运行 `run_perf_test.py`，确认 <20% |
| **栈溢出** | se_main 类似问题重现 | TMalign_main 不是 se_main（函数体结构不同），概率极低 |

---

## 七、调用链验证（翻转后）

```
USalign.cpp TMalign()  xa/ya=Coords
  → TMalign_main(Coords&, Coords&, ...)  [真实现, 行 5782]
    → get_initial(..., xa, ya, ...)        Coords& overload
    → detailed_search(..., xa, ya, ...)    Coords& overload
    → DP_iter(..., xa, ya, ...)            Coords& overload
    → approx_TM(..., xa, ya, ...)          Coords& overload (步骤 1)
    → get_initial_ssplus(..., xa, ya, ...)  Coords& overload (步骤 2)
    → get_initial5(..., xa, ya, ...)        Coords& overload
    → get_initial_fgt(..., xa, ya, ...)     Coords& overload
    → standard_TMscore(..., xa, ya, ...)    Coords& overload
    → detailed_search_standard(..., xa, ya, ...) Coords& overload
    → do_rotation(xa, xt, ...)             basic_fun.h:872 Coords&,Coords&
    → dist(&ya[j][0], &xt[i][0])           dist(double*, double*)

MMalign.h MMalign_search  xa/ya=Coords
  → TMalign_main(Coords&, Coords&, ...)  [真实现, 行 5782]  (同上)

flexalign.h flexalign_main  xa/ya=double**
  → TMalign_main(double**, double**, ...) [包装器, 行 4906]
    → 构造 Coords xa_tmp, ya_tmp → TMalign_main(Coords&, Coords&, ...) [真实现]
```

**性能影响**：
- USalign.cpp 和 MMalign.h 调用路径：零开销（直接调 Coords& 真实现，无包装层）
- flexalign.h/MMalign.cpp/qTMclust.cpp/TMalign.cpp 路径：O(n) 拷贝（double** → Coords），这些都不是最热路径，一次性拷贝可忽略
- **热路径（Kabsch 迭代内）完全零开销**
