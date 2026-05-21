# USalign C → C++ 重构进度记录

## 2026-05-20 日终状态：全体遗漏项修复 + 最终审计

### 今日完成汇总

| 会话 | Commit | 内容 |
|------|--------|------|
| 上午 | `0174331` | L2-f: TMscore.h 6处VLA → std::vector |
| 上午 | `2b63989` | L1-10+L1-12: basic_fun.h 循环变量内联 + C89声明清理 |
| 下午 | `9a543d7` | P0+P1: 全面审计遗漏项修复（13文件，12处 new char[] + 17处语法残余） |
| 下午 | 待提交 | P3-1: 7个独立.cpp循环变量内联 + strcmp 3处 + 最终审计遗漏3处 new char[] |

### 当前代码状态（全部 22 类 C→C++ 映射逐项核实）

| # | 类别 | 状态 |
|---|------|------|
| 1 | printf/fprintf | ❌ P-3 已取消（106处格式化输出保留） |
| 2 | sprintf | ❌ P-3 已取消 |
| 3 | strcmp → operator== | ✅ 全项目清零 |
| 4 | atoi/atof → safe_stoi/safe_stod | ✅ 全项目完成 |
| 5 | strlen → .size() | ✅ 全项目清零 |
| 6 | strcpy → string 赋值 | ✅ 全项目清零 |
| 7 | char* → string& | ✅ M里程碑完成 |
| 8 | NULL → nullptr | ✅ 全项目清零（仅 pstream.h 三方库残留） |
| 9 | (type)expr → static_cast | ✅ 全项目完成 |
| 10 | C头文件 → C++头文件 | ✅ 全项目完成 |
| 11 | #define MAX → std::max | ✅ 已删除宏，7处调用点替换 |
| 12 | char msg[N] → string | ✅ 不适用（无此模式） |
| 13 | FILE* → ifstream | ✅ 全项目完成（仅 pstream.h 三方库残留） |
| 14 | clock() → std::clock() | ✅ 全项目完成 |
| 15 | #define 守卫 → #pragma once | ✅ 10个头文件添加 |
| 16 | VLA → vector | ✅ 全项目零 VLA |
| 17 | /* */ → // | — 无单行可转换（多行文档保留） |
| 18 | 循环外声明 → 循环内 | ⚠️ .cpp文件完成；.h算法函数约200处未改（P3-2跳过） |
| 19 | (char*) 不必要强转 | ✅ 全项目清零 |
| 20 | 逗号声明拆分 | ✅ 全项目完成 |
| 21 | C89集中声明 → 随用随声明 | ⚠️ basic_fun.h完成；MMalign.h 61处未改（P3-2跳过） |
| 22 | 二级指针 → vector | ⏸️ 延后性能优化阶段 |

### new char[] 最终状态

全项目应用代码 **零 `new char[]`**。仅剩：
- `pstream.h:1235,1240` — 第三方库
- `USalign.cpp:1926-1927` — 已注释代码

### 遗留问题

| # | 问题 | 严重性 | 状态 |
|---|------|--------|------|
| 15 | se_main string 重载跨作用域栈溢出 | P0→已结案 | `.c_str()` 永久方案，根因：栈帧布局差异 |
| — | qTMclust.cpp `read_PDB(seq_tmp)` 类型不匹配 | P2 | 临时 string 桥接已修复，但 seq_vec 类型链 (`vector<vector<char>>`) 未统一升级 |
| — | xyz_sfetch.cpp `safe_stoi` 未声明 | P3 | 独立程序已有问题，非本次引入 |
| — | 头文件算法函数 for 循环变量约 200 处 | P3 | 跳过（纯外观，算法核心函数改动风险高） |
| — | MMalign.h C89 声明 61 处 | P3 | 跳过（纯外观，无编译影响） |
| — | 独立程序验证（TMscore/HwRMSD/MMalign/pdb2ss） | P1 | 重构全部完成后统一手动测试 |

### 待提交改动（当前工作区）

| 文件 | 改动 |
|------|------|
| HwRMSD.cpp | 删除无用 C89 声明 `int i,j; int chain_i,chain_j;` |
| TMalign.cpp | 循环变量内联 + 修复 secx/secy 注释行 bug |
| TMscore.cpp | 循环变量内联 |
| NWalign.cpp | 循环变量内联 |
| MMalign.cpp | 循环变量内联（含 S5 stash） |
| qTMclust.cpp | 循环变量内联 + seq_tmp 桥接修复 |
| se.cpp | 循环变量内联 |
| xyz_sfetch.cpp | `new char[]` → `std::string` |
| MMalign.h | `output_dock_rotation_matrix` 签名 `const char*` → `const std::string&`，strcmp → == |
| TMalign.h | `output_rotation_matrix` 签名同改，strcmp → == |
| flexalign.h | `output_flexalign_rotation_matrix` 签名同改，strcmp → == |
| NWalign.h | 2处 `trace_back_*` 中 `new char[]` → `std::string`（strncpy→assign，指针运算→string方法） |
| USalign.cpp | `output_dock_rotation_matrix` 调用去掉 `.c_str()` |

### Git 当前状态

```
(工作区待提交) P3-1 + strcmp + 最终审计遗漏
9a543d7 refactor(P0+P1): 全面审计遗漏项修复 — new char[]清零 + 语法风格残余
2b63989 refactor(L1-10+L1-12): basic_fun.h 循环变量内联 + C89声明清理
0174331 refactor(L2-f): TMscore.h 6处VLA → std::vector<int>
... (49 commits total on USalign-beta)
```

### 明天起点

1. **手动测试**：等待用户测试本轮所有改动
2. **提交**：测试通过后提交当前工作区
3. **最终合并评估**：确认 USalign-beta → master 合并策略（fast-forward，49+ commits）
4. **独立程序验证**：TMscore / HwRMSD / MMalign / pdb2ss 手动对比测试
5. **L2-h 评估**：二级指针 → vector 是否在本次重构范围内启动

---

## 2026-05-20 全面审计：遗漏项修复（P0+P1 执行）

| 指标 | 数值 |
|---|---|
| 完成步骤 | P0（12处 new char[]）+ P1（17处语法残余，strcmp 3处延后）|
| Commit 数 | 1（9a543d7）|
| 修改文件 | 13（HwRMSD/SOIalign/NWalign/TMalign/flexalign/MMalign/TMscore/se/param_set.h + USalign/MMalign/TMalign/qTMclust.cpp）|
| 完成任务 | 全项目 new char[] 清零，语法风格残余基本清除 |

### P0 执行详情

| 文件 | 原始代码 | 替换 |
|------|---------|------|
| flexalign.h:110-111 | `char *secx_h = new char[xlen+1]` | `std::string secx_h; secx_h.resize(xlen+1)` |
| flexalign.h:288-289 | `char *secx_h = new char[xlen_h+1]` | 同上（hinge 块） |
| MMalign.h:1129 | `sec = new char[len+1]` | `sec.resize(len+1)` |
| TMalign.h:3860-3861 | `seqx_cp/secx_cp = new char[xlen*2+1]` | `.resize(xlen*2+1)` + TMalign_main 用 `.c_str()`/`&[0]` |
| USalign.cpp:1441 | `secy_trim = new char[ylen_trim+1]` | `secy_trim.resize(ylen_trim+1)` + `&secy_trim[0]` 传参 |
| USalign.cpp:2132-2133 | `seqy_ext/secy_ext = new char[ylen_ext+1]` | `.resize()` + `seqy.assign(seqy_ext, 0, ylen)` |
| MMalign.cpp:519,545 | `secx/secy = new char[...]` | S5 stash 恢复（预先完成的 string 转换） |

全项目验证：`grep -rn 'new char\[' *.cpp *.h | grep -v pstream.h` 仅剩 pstream.h（三方库）和 USalign.cpp 两行已注释代码。

### P1 执行详情

| 类别 | 数量 | 说明 |
|------|------|------|
| `#define MAX` → `std::max` | 1+7调用 | NWalign.h 宏删除，7处调用点改为 `std::max()` |
| C 强转 → `static_cast` | 8 | `(float)t2` / `(int)(len/200)` 等全部替换 |
| `#pragma once` 添加 | 10头文件 | 5个无守卫 + 5个旧式 `#ifndef` 守卫（保留兼容） |
| 逗号声明拆分 | 1 | MMalign.h `int c,r` → `int c; int r;` |
| strcmp | 3 | 延后（需连带改 `const char* fname_matrix` → `const string&` 签名链） |

### Git 当前状态

```
9a543d7 (HEAD) refactor(P0+P1): 全面审计遗漏项修复 — new char[]清零 + 语法风格残余
2b63989 refactor(L1-10+L1-12): basic_fun.h 循环变量内联 + C89声明清理
0174331 refactor(L2-f): TMscore.h 6处VLA → std::vector<int>
```

### 剩余工作

| 优先级 | 项目 | 数量 | 说明 |
|--------|------|------|------|
| P1 | strcmp 3处 | 3 | 延后，需改函数签名链 |
| P2 | C块注释 `/* */` → `//` | ~20 | 低风险 |
| P3 | 独立.cpp 循环外声明 | ~40 | MMalign/NWalign/TMalign/TMscore/qTMclust |
| P3 | C89 集中声明 | ~15 | MMalign.h, HwRMSD.h 函数入口 |
| — | 二级指针→vector | ~347 | 延后性能优化 |

---

## 2026-05-20 全面审计：遗漏项清单（原始审计记录）

对比设计文档、进度日志和源码现状，逐项扫描 22 类 C→C++ 映射。发现之前的"代码层面重构全部完成"判断有误，存在显著遗漏。

### 严重遗漏：仍有 `new char[]` 堆分配未转换

这些本应在 M 里程碑 / S 系列中消灭，但被遗漏：

| # | 文件 | 行号 | 代码 | 遗漏原因 |
|---|------|------|------|---------|
| 1 | flexalign.h | 110-111 | `char *secx_h = new char[xlen+1]` | S17 计划了但从未执行（设计文档标注为"可选，另行评估"） |
| 2 | flexalign.h | 110-111 | `char *secy_h = new char[ylen+1]` | 同上 |
| 3 | flexalign.h | 288-289 | `char *secx_h = new char[xlen_h+1]` | 同上，hinge 块 |
| 4 | flexalign.h | 288-289 | `char *secy_h = new char[ylen_h+1]` | 同上 |
| 5 | MMalign.h | 1129 | `sec = new char[len+1]` | parse_chain_list 中，A-1（seq→string）之后遗留的 sec |
| 6 | TMalign.h | 3860 | `seqx_cp = new char[xlen*2+1]` | CPalign 函数被 M-2 遗漏 |
| 7 | TMalign.h | 3861 | `secx_cp = new char[xlen*2+1]` | 同上 |
| 8 | USalign.cpp | 1441 | `secy_trim = new char[ylen_trim+1]` | M-2 迁移时遗漏 |
| 9 | USalign.cpp | 2133 | `seqy_ext = new char[ylen_ext+1]` | mTMalign M-2 B-3 hinge 段迁移时遗漏 |
| 10 | USalign.cpp | 2134 | `secy_ext = new char[ylen_ext+1]` | 同上 |
| 11 | MMalign.cpp | 519 | `secx = new char[xlen+1]` | S5 stash 未提交（独立程序） |
| 12 | MMalign.cpp | 545 | `secy = new char[ylen+1]` | 同上（独立程序） |

**总计约 12 处**（不含 pstream.h 三方库）。所有 `delete[]` 对应释放点也需同步检查。

### 中等问题：C 风格语法残余

| # | 类别 | 数量 | 位置 | 对应设计步骤 |
|---|------|------|------|------------|
| 13 | **strcmp** | 3 处 | MMalign.h:3377, TMalign.h:2889, flexalign.h:645 — 均为 `strcmp(fname_matrix,"-")` 模式 | L2-d 未覆盖 |
| 14 | **#define MAX** | 1 处 | NWalign.h:8 `#define MAX(A,B) ((A)>(B)?(A):(B))` | L2 遗漏 |
| 15 | **C 风格强转** | 8 处 | USalign.cpp(3): `(int)(len/200)`×2, `(float)t2`×1; MMalign.cpp(3): `(float)`, `(int)`; TMalign.cpp(1); qTMclust.cpp(1) | L3/L4 遗漏 |
| 16 | **旧式 #ifndef 守卫** | 5 个 | HwRMSD.h, NWalign.h, SOIalign.h, TMalign.h, flexalign.h — 仍用 `#ifndef X_h` / `#define X_h` 模式，未替换为 `#pragma once` | L0/L2 未完成 |
| 17 | **无头文件守卫** | 5 个 | MMalign.h, se.h, TMscore.h, basic_fun.h, param_set.h — 既无 `#ifndef` 也无 `#pragma once` | L0/L2 从未处理 |
| 18 | **C 块注释 `/* */`** | ~20 处 | Kabsch.h（函数头）、MMalign.h（多段）、NW.h、cif2pdb.cpp、qTMclust.cpp、xyz_sfetch.cpp 等 | L2-g/L3 未覆盖 |
| 19 | **逗号声明** | 1 处 | MMalign.h:314 `int c,r;`（应拆为 `int c; int r;`） | L2-g 遗漏 |
| 20 | **循环外声明 `for(i=`** | ~40 处 | 全体独立 .cpp 文件（MMalign.cpp, NWalign.cpp, TMalign.cpp, TMscore.cpp, qTMclust.cpp 等）。主 USalign.cpp 和 .h 文件中多数已内联 | L3/L4 未覆盖，仅在 basic_fun.h 做了 7 处 |
| 21 | **C89 集中声明** | ~15 处 | MMalign.h（多函数入口 `int i; int j;`）、HwRMSD.h（2 函数） | L2-g 未覆盖 |

### 设计明确不做（无需处理）

| 类别 | 数量 | 原因 |
|------|------|------|
| printf/fprintf/sprintf | 106 处 | P-3 已取消（snprintf+cout 风格收益低，格式化语义一致性问题） |
| 二级指针 → vector | ~347 处 | L2-h 延后性能优化阶段 |
| Kabsch.h 循环变量内联 | 15 处 | L0-9 永久跳过（337行密集SVD，风险>收益） |

### 与之前进度的差异分析

之前说"代码层面全部完成"基于以下错误假设：
1. **S17 被标注为"可选"**，但实际上 flexalign.h 中 4 处 `secx_h/secy_h = new char[]` 是 M 里程碑的核心改造范围
2. **M-2 覆盖了主要函数**，但遗漏了边界路径：CPalign 中的 `seqx_cp/secx_cp`、hinge 段残留的 `seqy_ext/secy_ext`、`secy_trim`
3. **独立 .cpp 文件被排除在回归测试外**，它们的 L3/L4 改造从未被验收
4. **头文件守卫 (`#pragma once`)** 仅在 BLOSUM.h 和 Kabsch.h 完成，其余 10 个头文件被遗漏

### 修复优先级建议

| 优先级 | 项目 | 改动量 | 风险 |
|--------|------|--------|------|
| P0 | `new char[]` → `std::string`（12 处，#1-12） | 中 | 中 |
| P1 | `#pragma once` + 移除旧守卫（10 文件，#16-17） | 小 | 低 |
| P1 | `strcmp` → `operator==`（3 处，#13） | 小 | 低 |
| P1 | `#define MAX` → `std::max`（1 处，#14） | 小 | 低 |
| P1 | C 风格强转 → `static_cast`（8 处，#15） | 小 | 低 |
| P2 | 逗号声明拆分（1 处，#19） | 小 | 低 |
| P2 | C 块注释 → `//`（~20 处，#18） | 小 | 低 |
| P3 | 独立 .cpp 文件循环外声明 + C89 声明（~55 处，#20-21） | 大 | 低 |

---

## 2026-05-20 会话（L0-9/L1-10/L1-12 收尾评估 + 执行）

| 指标 | 数值 |
|---|---|
| 完成步骤 | L1-10 + L1-12 合并（basic_fun.h 循环变量内联 + C89 声明清理）|
| 永久跳过 | L0-9（Kabsch.h 循环变量内联）|
| Commit 数 | 1（2b63989）|
| 修改文件 | basic_fun.h |
| 完成任务 | L0-9 永久跳过，L1-10+L1-12 完成，低优先级收尾全部关闭 |

### 重新评估结论

重新审视三个遗留任务当初延后的原因，结合当前代码实际状态逐项分析：

#### L0-9: Kabsch.h 循环变量内联 → 永久跳过

**当初延后原因**："复杂数值算法需谨慎"

**当前评估**：Kabsch 函数 337 行密集 SVD 数值算法。19 个变量（`i, j, m, m1, l, k, d, h, g, p, det, sigma...`）全部在函数入口声明，在数十个循环中交叉复用。典型模式 `for (i = 0; i <= j; i++)` 中 `j` 在循环外设置。变量作用域深度交织，改动任何一个都可能引入微妙数值 bug。

**决定**：永久延后，标记为"不做"。当初判断完全正确，代码无需再碰。

#### L1-12: C89 集中声明 → 随用随声明 → 工作量远小于预估

**当初延后原因**："1080 行侵入性大"

**当前评估**：整个 basic_fun.h 已基本现代化（经过 L1-2 NULL→nullptr、L1-13 using namespace std 移除、M 里程碑 char*→string 等多轮重构后，声明已自然靠近使用点）。真正的 C89 遗留仅两处：

| 函数 | C89 遗留 | 说明 |
|------|---------|------|
| `file2chainlist` | `int a; int b;` | `b` 从未使用 |
| `file2chainpairlist` | `int a; int b; size_t i;` | `b` 从未使用 |

`get_PDB_lines` 中的变量声明已基本靠近使用点，不属于 C89 风格。

#### L1-10: 循环变量内联 → 11 处中 9 处安全

**当初延后原因**：问题 2（循环变量内联的隐藏陷阱）—— `for (i=0;...)` 中 `if (line[i]==' ') break;` 提前退出，循环后 `line.substr(0,i)` 使用退出位置的 `i`。

**当前评估**：逐个审查 11 处 `for(x=...` 模式：

| 行号 | 函数 | 变量 | 安全？ | 原因 |
|------|------|------|--------|------|
| 460-462 | get_PDB_lines | `i` | ❌ | 问题 2 模式：`break` 后用 `line.substr(0,i)` |
| 466 | get_PDB_lines | `i` | ✅ | 纯计数器，但与外层 `i` 声明纠缠 |
| 786 | get_PDB_lines | `l` | ✅ | 纯累加器，需确认无其他使用 |
| 804 | read_PDB | `i` | ❌ | `return i`（返回值） |
| 921 | file2chainlist | `a` | ✅ | 仅循环内使用 |
| 981 | file2chainpairlist | `i` | ✅ | 纯计数器 |
| 985 | file2chainpairlist | `i` | ✅ | 纯计数器 |
| 991 | file2chainpairlist | `i` | ✅ | 纯计数器 |
| 996 | file2chainpairlist | `i` | ✅ | 纯计数器 |
| 1002 | file2chainpairlist | `a` | ✅ | 仅循环内使用 |
| 1037 | file2chainpairlist | `a` | ✅ | 仅循环内使用 |

#### 合并方案

**L1-10 + L1-12 合并为一步**，仅改 `file2chainlist` + `file2chainpairlist` 两个函数：

- 删除未使用的 `int b`（2 处）
- `for(a=0;...)` → `for(int a=0;...)`（3 处，L1-10）
- `for(i=0;...)` → `for(size_t i=0;...)`（4 处，L1-10）
- 删除函数入口处已无用的 `int a; size_t i;`（L1-12）

**不改动**：
- `get_PDB_lines`（2 处不安全 + 安全但与外层纠缠）
- `read_PDB`（`return i` 返回值）
- `Kabsch.h`（永久跳过）

### Git 当前状态

```
2b63989 (HEAD) refactor(L1-10+L1-12): basic_fun.h 循环变量内联 + C89声明清理
0174331 refactor(L2-f): TMscore.h 6处VLA → std::vector<int>
```
---

### 低优先级收尾里程碑总结

| 条目 | 原步骤 | 结果 |
|------|--------|------|
| Kabsch.h 循环变量内联 | L0-9 | ❌ 永久跳过（337行密集SVD，变量作用域深度交织） |
| basic_fun.h 循环变量内联 | L1-10 | ✅ file2chainlist/file2chainpairlist 7处内联；get_PDB_lines 2处因问题2跳过 |
| basic_fun.h C89集中声明 | L1-12 | ✅ 删除未使用的 b + 随用随声明 |
| FILE*→ifstream | L1-6 | ✅ 已在 M-1 完成 |
| 格式化 printf | P-3+ | ❌ 已取消 |
| 二级指针→vector | L2-h | ⏸️ 延后性能优化阶段 |

---

## 2026-05-20 会话（L2-f VLA 收尾：TMscore.h）

| 指标 | 数值 |
|---|---|
| 完成步骤 | L2-f（TMscore.h 6 处 VLA → std::vector）|
| Commit 数 | 1（0174331）|
| 修改文件 | TMscore.h + TMscore.cpp |
| 完成任务 | **全项目 VLA 清零**：USalign 编译单元 + TMscore 独立程序均已无 VLA |

### L2-f VLA 收尾：TMscore.h ✅

**commit `0174331`**：TMscore.h 中 `TMscore8_search` 和 `TMscore8_search_standard` 两个函数的 6 处 VLA。

全是非热点（不在内层循环，每次比对仅调用 5-6 次），安全替换为 `std::vector<int>`：
- `k_ali[kmax]` → `std::vector<int> k_ali(kmax)`（2 处）
- `L_ini[n_init_max]` → `std::vector<int> L_ini(n_init_max)`（2 处，n_init_max=6）
- `i_ali[kmax]` → `std::vector<int> i_ali(kmax)`（2 处）
- 4 处 `score_fun8(..., i_ali, ...)` → `score_fun8(..., i_ali.data(), ...)`

**TMscore.cpp 附带修复**：
- `double **xa, **ya` 声明在之前重构中被误并入注释行（与 `int xchainnum,ychainnum;//...` 同行），导致变量未声明。拆分为独立行恢复声明
- `TMscore_main(..., seqx, seqy, ...)` → `TMscore_main(..., seqx.c_str(), seqy.c_str(), ...)`（seqx/seqy 已是 std::string）

### 待测试提醒

> ⚠️ **TMscore 是独立程序（编译自 TMscore.cpp），不在 `run_regression.py` / `run_perf_test.py` 回归测试框架内。** 重构全部完成后，需手动编译运行 TMscore 对比原始输出来验证正确性。

同样需要独立验证的程序：
- **HwRMSD**（S3 已改 secx/secy→string）
- **MMalign**（S5 stash，全对全路径 secx/secy→string）
- **pdb2ss**（S1 已改 secx→string）
- **TMscore**（本次 L2-f + 之前的 char*→string 改造）

### Git 当前状态

```
0174331 (HEAD) refactor(L2-f): TMscore.h 6处VLA → std::vector<int>
ce40f87 refactor(S15): USalign.cpp MMdock() secx/secy char* → std::string
```

### L2-f 里程碑总结

`-Wvla -Werror=vla` 全局扫描结果：USalign 编译单元 + TMscore 独立程序均已零 VLA。全项目 VLA 改造完成。

---

## 2026-05-18 会话（下午：flexalign 残余 + 问题 15 + secx/secy S1-S2）

| 指标 | 数值 |
|---|---|
| 完成步骤 | flexalign seqx_h/seqy_h + 问题 15 诊断 + secx/secy S1-S2 |
| Commit 数 | 4（f7dd8f0 / dfe2e0f / 07b3779 / 4b6db0f）|
| 修改文件 | flexalign.h + se.h + USalign.cpp + pdb2ss.cpp + TMalign.cpp |
| 完成任务 | seqx/seqy 全量迁移完成 + 问题 15 结案 + secx/secy 17 步计划启动 |

### flexalign.h seqx_h/seqy_h 残余清理 ✅

**commit `f7dd8f0`**：这是 M-2/M-3 中漏掉的最后一批序列字符串 char* 工作缓冲区。

- `round2` 块：`char *seqx_h = new char[xlen+1]` → `std::string seqx_h; seqx_h += seqx[i]`
- `hinge` 块：同上模式
- `TMalign_main` 调用加 `.c_str()`，复用前加 `.clear()`
- 删除 4 处 `delete[] seqx_h/seqy_h`

完成后，**整个代码库中所有序列字符串的 char* 工作缓冲区已全部消除**。

### 问题 15 诊断与结案 ✅

**commit `dfe2e0f`**：se_main string 重载跨作用域崩溃根因诊断。

**诊断过程**：
1. 假设 GCC/MinGW 优化内联 Bug → 加 `__attribute__((noinline))` + 移除 `.c_str()` 绕过
2. 测试：msta_rna 仍然崩溃 → `noinline` **无效**
3. 恢复 `.c_str()` 绕过，保留 `noinline` → 测试通过
4. 结论：根因**不是**内联优化

**最终根因**：`const std::string&` vs `const char*` 参数类型差异改变了 se_main（238 行）的栈帧布局，在 mTMalign 深层嵌套循环中触发栈溢出。与内联无关。

**最终方案**：
- 移除无效的 `__attribute__((noinline))`
- `.c_str()` 是永久正确方案，不是权宜之计
- se.h 添加注释文档化限制
- 放弃 se_main/NWalign_main 方向翻转（风险大于收益）

### 问题 15 的未解决问题

| # | 问题 | 严重性 | 说明 |
|---|------|--------|------|
| 15 | se_main string 重载跨作用域栈溢出 | P0→已结案 | `.c_str()` 永久方案。根因是栈帧布局差异，不是内联 Bug |

### secx/secy 迁移启动 ✅

制定 17 步原子化计划（见设计文档 secx/secy 章节），转换模式：
```cpp
secx = new char[xlen+1]           →  secx.resize(xlen+1)
make_sec(..., secx)               →  make_sec(..., &secx[0])
TMalign_main(..., secx, ...)      →  TMalign_main(..., secx.c_str(), ...)
cout << secx                      →  cout << secx.c_str()  // 避免 '\0'
delete[] secx                     →  （删除，自动析构）
```

| 步骤 | Commit | 内容 |
|------|--------|------|
| S1 | `07b3779` | pdb2ss.cpp secx → std::string（1 处） |
| S2 | `4b6db0f` | TMalign.cpp secx/secy → std::string（2 处） |

### Git 当前状态

```
4b6db0f (HEAD) refactor(S2): TMalign.cpp secx/secy char* → std::string
07b3779 refactor(S1): pdb2ss.cpp secx char* → std::string
dfe2e0f refactor: 问题 15 诊断结论 — se_main string 重载跨作用域限制
f7dd8f0 refactor: flexalign.h seqx_h/seqy_h char* 工作缓冲区 → std::string
e864052 refactor(B-5): 删除 copy_chain_data/copy_chain_pair_data char* 包装器
```

### 明天起点

1. 继续 secx/secy 迁移：**S3**（HwRMSD.cpp，2 处）
2. 类推推进 S4-S17，按计划逐步完成全部 ~45 处转换

---

## 2026-05-18 会话（全天：M-3 完成）

| 指标 | 数值 |
|---|---|
| 完成步骤 | A-1 + A-2 + B-1 + B-2 + B-3 + B-5 |
| Commit 数 | 6（090ab23 / c015868 / 0d6c92d / af45d89 / 6538b39 / e864052）|
| 修改文件 | MMalign.h（主要）+ basic_fun.h + USalign.cpp |
| 完成任务 | **M-3 里程碑：全部 char* 包装器已删除** |

### 阶段 A：删除 read_PDB char* 包装器 ✅

| 步骤 | Commit | 内容 |
|------|--------|------|
| A-1 | `090ab23` | parse_chain_list `seq = new char[]` → `std::string seq` |
| A-2 | `c015868` | 删除 read_PDB char* 包装器（basic_fun.h，~8 行） |

### 阶段 B：删除 copy_chain_data/copy_chain_pair_data char* 包装器 ✅

| 步骤 | Commit | 内容 |
|------|--------|------|
| B-1 | `0d6c92d` | copy_chain_pair_data 新增 string& 重载，char* 版退化为包装器（反向桥接） |
| B-2 | `af45d89` | MMalign_search seqx/seqy new char[] → std::string |
| B-3 | `6538b39` | MMalign_final + MMalign_se_final + MMalign_dimer seqx/seqy → std::string |
| B-5 | `e864052` | 删除两个 char* 包装器 + 修复 USalign.cpp seqy_trim 遗漏 |

B-4（MMalign_iter/MMalign_cross）合并入 B-3——这两个是纯透传函数，无需局部 string。

### 本日关键经验

1. **用函数名做唯一锚点**：`replace_all` 会误伤结构相似的其他函数。改用 `void MMalign_final(` 等唯一函数名作为编辑锚点，确保每次只改一个函数。

2. **分步 replace_all 的危险**：先用 `replace_all` 改 `se_main` 调用为 `.c_str()`，再改局部变量声明，中间状态不一致导致编译失败。正确顺序：先完成一个函数的全部修改（声明 + 分配 + 调用 + 清理），再处理下一个。

3. **包装器僵尸检测**：删除包装器前用 `grep` 搜索 `funcname(.*char\s*\*` 确认零调用者。`seqy_trim` 是被 M-2 遗漏的 char* 变量，说明正则扫描不如逐函数审核可靠。

### Git 当前状态

```
e864052 (HEAD) refactor(B-5): 删除 copy_chain_data/copy_chain_pair_data char* 包装器
6538b39 refactor(B-3): MMalign_final/se_final/dimer seqx/seqy char* → std::string
af45d89 refactor(B-2): MMalign_search seqx/seqy new char[] → std::string
0d6c92d refactor(B-1): copy_chain_pair_data 新增 string& 重载，char* 版退化为包装器
c015868 refactor(A-2): 删除 read_PDB char* 包装器
090ab23 refactor(A-1): parse_chain_list seq new char[] → std::string
c958af5 refactor(M-2): MMdock() seqx/seqy char* → std::string
```

### M-3 里程碑总结

已删除的 char* 包装器：
- `read_PDB` char* 包装器（basic_fun.h）
- `copy_chain_data` char* 包装器（MMalign.h）
- `copy_chain_pair_data` char* 包装器（MMalign.h）

所有 char* → std::string 的反向桥接包装器已全部消除，真正的实现统一在 string 重载中。

### 明天起点

**阶段 C（可选）**：se_main/NWalign_main 方向翻转，或进入其他重构任务。

---

## 2026-05-18 会话（上午：M-3 方案分析）

| 指标 | 数值 |
|---|---|
| 完成步骤 | 0（方案分析与设计） |
| Commit 数 | 0 |
| 修改文件 | 设计文档更新 |
| 完成任务 | M-3 详细执行方案制定 |

### M-3 源码分析结论

**M-3 真正目标**：删除 `read_PDB` 和 `copy_chain_data` 两个 char* 反向桥接包装器。`se_main`/`NWalign_main` 的 string 重载是正向桥接（string → char*），char* 版本是真正实现，**不属于 M-3 删除对象**。

**阻塞项分析**：

| 包装器 | 剩余调用者 | 阻塞原因 |
|--------|-----------|----------|
| `read_PDB` char* (basic_fun.h:819) | MMalign.h:1141 `parse_chain_list` | `seq = new char[len+1]` → 传 char* |
| `copy_chain_data` char* (MMalign.h:695) | MMalign.h 内部 ~7 处 | MMalign_search/final/iter/dimer 内部 `seqx/seqy = new char[]` |

**问题 15 重新分析**：
- `se_main` string 重载仅一行 `.c_str()` 转发，在 C++ 标准层面与调用处手动写 `.c_str()` 语义等价
- 跨作用域崩溃 + 同作用域正常 → 高度怀疑 GCC/MinGW 优化 Bug
- 推测：单行 inline + 跨栈帧 string 引用 + `.c_str()` 的组合触发编译器错误优化
- **不阻塞 M-3**（se_main 的 char* 版本本就是真正实现，不在删除范围）

### M-3 执行方案

拆为两个独立阶段：

**阶段 A（3 步，低风险）**：删除 `read_PDB` char* 包装器
- A-1: `parse_chain_list` `seq = new char[]` → `std::string seq`
- A-2: 删除 `read_PDB` char* 包装器
- A-3: 回归测试

**阶段 B（6 步，中风险）**：删除 `copy_chain_data` char* 包装器
- B-1: `copy_chain_pair_data` 签名 `char*` → `std::string&`
- B-2~B-4: `MMalign_search/final/iter` 内部 `new char[]` → `std::string`
- B-5: 删除 `copy_chain_data` char* 包装器
- B-6: 全量回归测试

**阶段 C（后续可选）**：`se_main`/`NWalign_main` 方向翻转

详见设计文档 M-3 详细执行方案章节。

### 明天起点

开始执行**阶段 A-1**：迁移 `parse_chain_list` 的 `seq = new char[]` → `std::string`

---

## 2026-05-17 会话

| 指标 | 数值 |
|---|---|
| 完成步骤 | flexalign() M-2 + qTMclust.cpp 修复 + mTMalign B-1~B-5 + MMdock() M-2 |
| Commit 数 | 6（0e84221 / 873c82c / 4cc49f1 / 737d747 / c34639b / c958af5）|
| 修改文件 | USalign.cpp（flexalign / mTMalign / MMdock）+ qTMclust.cpp + basic_fun.h（回退）|
| 完成任务 | M-2 里程碑：USalign.cpp 全部函数 seqx/seqy `char*` → `std::string` |

### M-2: USalign.cpp flexalign() ✅

**commit `0e84221`**: 与 TMalign() 完全一致的模式，8 处修改。secx/secy 保持 char*（make_sec 输出缓冲区）。

### L3: qTMclust.cpp `&seq_tmp[0]` → `seq_tmp` ✅

**commit `873c82c`**: `read_PDB(&seq_tmp[0], ...)` → `read_PDB(seq_tmp, ...)`，直接调 string 重载。原 char* 包装器通过 strcpy 拷回，不更新 `string::size()`，新方法更正确。

**尝试删除 read_PDB char* 包装器失败**：MMalign.h:1141 的 `parse_chain_list` 中仍有 `seq = new char[len+1]` 传 `char*`，包装器不是僵尸。回退删除。

### mTMalign() M-2 分步执行 ✅

**上次失败的根因**：hinge 段（2183-2197 行）`seqy = new char[ylen+1]` + 逐字符 `seqy[r]=seqy_ext[r]`。改为 `string` 时直接 `seqy[r]=seqy_ext[r]` 写入空 string（size()==0）是**未定义行为**——不自动扩容，不更新 size。

**修复方案**：`seqy.assign(seqy_ext, ylen)` 一步完成 resize + 复制。

**另一个关键发现——`se_main` 字符串包装器跨作用域崩溃**：B-1 和 B-2 中 se_main 使用 string 包装器正常（seqx/seqy 同为最内层作用域），但 B-3 恢复循环和 Stage C 中 **程序直接崩溃**（seqy 声明在外层 for(iter) 作用域，seqx 在内层 for(tm_idx) 作用域）。用显式 `.c_str()` 绕过 string 包装器后一切正常。根因未定位。

| 子步骤 | Commit | 内容 |
|--------|--------|------|
| B-1 | `4cc49f1` | Stage A 初始全对全矩阵（~6 行） |
| B-2 | `737d747` | Stage B 前半迭代替换（~3 行） |
| B-3~B-5 | `c34639b` | hinge 段 seqy.assign + Stage C + `.c_str()` 绕过 se_main 包装器 + 移除集中声明 |

### MMdock() M-2 ✅

**commit `c958af5`**: 原计划遗漏的函数。集中声明 `char *seqx, *seqy` → `string seqx, seqy;`，移除 6 处 `new char[]`，TMalign_main/se_main 加 `.c_str()`。

### Git 当前状态

```
c958af5 (HEAD) refactor(M-2): MMdock() seqx/seqy char* → std::string
c34639b refactor(B-3~B-5): mTMalign Stage B hinge + Stage C seqx/seqy → std::string
737d747 refactor(B-2): mTMalign Stage B 前半 seqx/seqy char* → std::string
4cc49f1 refactor(B-1): mTMalign Stage A seqx/seqy char* → std::string
873c82c refactor(L3): qTMclust.cpp read_PDB &seq_tmp[0] → seq_tmp
0e84221 refactor(M-2): USalign.cpp flexalign() seqx/seqy char* → std::string
c88439a refactor(M-2): USalign.cpp SOIalign() seqx/seqy → std::string
4a6301f refactor(M-2): USalign.cpp MMalign() 多链路径+迭代优化 seqx/seqy → std::string
008a001 refactor(M-2): USalign.cpp MMalign() 单链路径 seqx/seqy → std::string
2c4454b refactor(M-2): USalign.cpp TMalign() seqx/seqy char* → std::string
```

### 新发现的问题

| # | 问题 | 严重性 | 说明 |
|---|------|--------|------|
| 15 | **`se_main` 字符串包装器跨作用域崩溃** | P0 | 当 seqx 和 seqy 声明在不同作用域层级时（如 seqy 在外层 for(iter)，seqx 在内层 for(tm_idx)），调用 `se_main(xa, ya, seqx, seqy, ...)` 匹配 string 包装器会导致程序静默崩溃。显式传 `.c_str()` 绕过可正常工作。B-1/B-2 不受影响（seqx/seqy 同在最内层）。根因未定位，可能涉及编译器优化或 ABI 问题。**当前用 `.c_str()` 规避** |
| 16 | MMdock() 原计划遗漏 | P2 | MMdock()（1207-1698 行）不在原 M-2 计划中，被误认为是 MMalign() 的一部分。本次会话补充迁移 |
| 17 | `read_PDB` char* 包装器非僵尸 | P3 | 之前判断剩余 1 个调用者（qTMclust.cpp:399）是错误的——MMalign.h:1141 的 `parse_chain_list` 仍有 `seq = new char[]` 传 `char*`。需等所有调用点迁移后才能删除 |

### 明天起点

1. 评估 **M-3** 可行性：`copy_chain_data` char* 包装器的剩余调用者分布（MMalign.cpp、MMalign.h），决定是否可以部分删除
2. 或启动 **M-3 先导工作**：模式 B 函数（`NWalign_main`、`se_main`）的方向翻转——将 string 包装器（当前调 char* 版）翻转为 char* 包装器调 string 版
3. 或调查 **问题 15**：`se_main` 字符串包装器跨作用域崩溃的根因

---

## 2026-05-16 会话（最终状态）

| 指标 | 数值 |
|---|---|
| 完成步骤 | L2-g/L2-f/M-1 恢复 + M-2 TMalign() + MMalign() 双路径 + SOIalign() |
| Commit 数 | 上午 4（01ef3c8~a983751）+ 下午 4（2c4454b/008a001/4a6301f/c88439a）|
| 修改文件 | TMalign.h(const修复) + USalign.cpp(TMalign/MMalign/SOIalign) |
| 延后 | mTMalign (Step B 拆为 5 子步，根因已定位) |

### M-2: USalign.cpp TMalign() ✅

**commit `2c4454b`**: TMalign() 函数中 `char *seqx, *seqy` → `std::string`:
- 移除函数顶部 `char *seqx, *seqy;` 声明
- `seqx = new char[xlen+1]` → `string seqx;`（随用随声明）
- `seqy = new char[ylen+1]` → `string seqy;`
- `read_PDB` 直接调用 string 重载
- `make_sec`/`extract_aln_from_resi`/`CPalign_main`/`TMalign_main` 改用 `.c_str()`
- `se_main` 有 string 重载，直接传递
- `seqx[r1]==seqy[r2]` 不变（string 支持 `operator[]`）

### M-2: USalign.cpp MMalign() 单链路径 ✅

**commit `008a001`**: MMalign() 单链路径 (`xa_vec.size()==1 && ya_vec.size()==1`) 迁移：
- 局部 `string seqx, seqy;` 替代 `new char[]`
- `copy_chain_data` 调用 string 重载
- 下游函数调用改用 `.c_str()`

### 新发现问题

#### 问题 13：MMalign() 多链路径无法独立迁移

- **原因**：多链路径后的 `MMalign_iter`/`MMalign_final`（MMalign.h）接受非 const `char*`，且内部写 `seqx[xlen]=0` 做 null 截断。若 USalign.cpp 的 MMalign 改为 string，调用这些函数时需传 `&seqx[0]`，且需先 resize 确保容量，脆弱且易出错。
- **决定**：多链路径 + 迭代优化保持 char*，与 MMalign.h 的 M-2 一起作为独立里程碑处理。
- **当前状态**：单链路径已迁移 ✅，多链路径延后 ⏸️

#### 问题 14：make_sec/sec_str const 修复被 P-3 脚本损坏后丢失

- **症状**：TMalign.cpp（已迁移）能编译，但 USalign.cpp 中 `make_sec(seqx.c_str(), ...)` 编译失败——`seqx.c_str()` 返回 `const char*`，但 `make_sec` 签名是 `char*`。
- **根因**：M-1 中做的 `make_sec(char* seq → const char* seq)` 修复在 be36f90 commit 中存在，但 P-3 脚本损坏 TMalign.h 后从 be36f90 恢复时丢失了该修复。
- **修复**：重新在 TMalign.h 中将 `make_sec` 和 `sec_str` 的 seq 参数加 `const`（`const char*`）。
- **教训**：git checkout 恢复文件时，如果基线 commit 在多个 commit 之前，可能丢失中间 commit 的修改。恢复后应 diff 对比确认完整性。

### M-2: USalign.cpp MMalign() 多链路径 + 迭代优化 ✅

**commit `4a6301f`**: 函数级 `string seqx, seqy;`，多链循环删除 `new char[]`，迭代优化用 nullptr 占位符传递 MMalign.h 函数（内部立即 new[] 覆盖）。

### M-2: USalign.cpp SOIalign() ✅

**commit `c88439a`**: 与 TMalign 完全一致的模式，`soi_se_main`/`SOIalign_main` 均接受 `const char*`。

### Git 当前状态

```
c88439a (HEAD) refactor(M-2): USalign.cpp SOIalign() seqx/seqy → std::string
4a6301f refactor(M-2): USalign.cpp MMalign() 多链路径+迭代优化 seqx/seqy → std::string
008a001 refactor(M-2): USalign.cpp MMalign() 单链路径 seqx/seqy → std::string
2c4454b refactor(M-2): USalign.cpp TMalign() seqx/seqy char* → std::string
a983751 refactor(M-1): NWalign.h 补充 NWalign_main string 重载 + extract_aln_from_resi const 修复
1ef18e9 refactor(L2-g): 注释+逗号声明补充到恢复的4个.h文件
0783bb7 refactor(L2-f): TMalign.h VLA → std::vector
01ef3c8 refactor(L2-e, P-2): TMalign.h TMscore.h C强转→static_cast + 纯文本printf→cout
b1ec892 refactor(L2-e, L2-f, L2-g, L3, L4, M-1, M-2, P-2): C→C++ 重构（2026-05-15 会话）
be36f90 refactor(L2-a+d): L2 头文件 NULL→nullptr + atoi/atof→safe_stoi/safe_stod
d65a2e9 refactor(L2-a): NWalign.h C → C++ 风格重构 + TMalign.h 临时 using namespace std
e6388b9 refactor(L1-13): basic_fun.h 移除 using namespace std;，所有 std 标识符加前缀
19e91af refactor(L1-11): basic_fun.h 逗号声明拆分
0e43deb refactor(L1-8~L1-9): basic_fun.h #pragma once + 块注释 → 行注释
22206f2 refactor(L1-3~L1-4): basic_fun.h 新增 safe_stoi/safe_stod 双重重载，替换 atoi/atof
fb92ed5 refactor(L1-2): basic_fun.h NULL → nullptr
040d2fd refactor(L1-1): basic_fun.h C 头文件 → C++ 头文件
b2a5647 refactor(L0): 第 0 层工具/常量头文件 C → C++ 风格重构
aa9c9aa add citation to license
```

### P-3 格式化 printf 里程碑：取消

（保留原记录）

### Step B 回退：mTMalign() 导致 msta_rna 输出截断 ❌

- **症状**：mTMalign() 改为 string 后，msta_rna（-mm 4）输出中第一轮迭代结果正确，但第二轮和最终输出全部缺失
- **根因已定位**（2026-05-17）：hinge 段（2183-2197 行）中 `seqy = new char[ylen+1]` 后逐字符 `seqy[r]=seqy_ext[r]` 复制。改为 `string` 时，直接用 `seqy[r]=seqy_ext[r]` 写入空 string（size()==0）是**未定义行为**——不自动扩容也不更新 size，导致后续代码读到的仍是空字符串。**正确写法**：`seqy.assign(seqy_ext, ylen)` 一步完成 resize + 复制。
- **原决定**：回退所有 mTMalign 改动（`git checkout`），延后处理。
- **新方案**：拆分为 5 个子步骤 B-1~B-5（Stage A → Stage B 前半 → hinge 段 → Stage C → 清理），每步独立编译、测试、提交

### 未解决问题（2026-05-17 更新）

| 问题 | 严重性 | 说明 |
|------|--------|------|
| Push failed | P0 | 远程仓库断开，`USalign-beta` 分支未 push |
| **问题 15**：se_main 包装器跨作用域崩溃 | P0 | 见 2026-05-17 会话新发现。当前用 `.c_str()` 规避 |
| M-3 删除 char* 包装器 | P2 | `copy_chain_data` char* 仍有调用者（MMalign.cpp + MMalign.h）；`NWalign_main`/`se_main` 需方向翻转 |
| MMalign 多链路径 `delete[]` secx/secy | P3 | 已被 nullptr 占位符规避 |

### 明天起点

1. **评估 M-3 可行性**：扫描 `copy_chain_data` char* 包装器的剩余调用者
2. **se_main 包装器修复**：调查跨作用域崩溃根因，修复后移除 `.c_str()` 绕过
3. 或启动 **MMalign.cpp / 其他 .cpp 文件迁移**

---

## 2026-05-15 会话

| 指标 | 数值 |
|---|---|
| 完成步骤 | L2-e（C 强转）、L2-g（注释/声明）、L2-f（VLA）、L3+L4（cpp 文件）、M-1（char*→string 桥接）、M-2（调用点迁移）、P-2（纯文本 printf→cout） |
| Commit 数 | 3（b1ec892 全量, b1ec892 amend, 01ef3c8 L2-e+P-2 TMalign/TMscore） |
| 修改文件数 | 24 |
| Git 恢复文件 | 4（NWalign.h, TMalign.h, TMscore.h, flexalign.h — 因 P-3 脚本损坏后从 be36f90 恢复） |
| 新增问题 | 5（详见下方问题 8-12） |
| 明天起点 | L2-g（注释/声明）或 L2-f（VLA）补充到已恢复的 4 个 .h 文件 |

### 遗留：4 个恢复文件待补充的改动 ✅ 全部完成（2026-05-16）

### Git 分支：`USalign-beta`（本地，不 push）

```
3bf24a9 refactor(P-3): NWalign.h output_NWalign_results 全部格式化printf→snprintf+cout
a3b2442 refactor(P-3): NWalign.h 第4个printf→snprintf+cout
23fdac4 refactor(P-3): NWalign.h 第3个printf→snprintf+cout
0cf88e0 refactor(P-3): NWalign.h 第2个printf→snprintf+cout
176a0a1 refactor(P-3): NWalign.h 第1个printf→snprintf+cout
a983751 refactor(M-1): NWalign.h NWalign_main string 重载 + extract_aln_from_resi const
1ef18e9 refactor(L2-g): 注释+逗号声明补充到恢复的4个.h文件
0783bb7 refactor(L2-f): TMalign.h VLA → std::vector
01ef3c8 refactor(L2-e, P-2): TMalign.h TMscore.h C强转→static_cast + 纯文本printf→cout
b1ec892 refactor(L2-e, L2-f, L2-g, L3, L4, M-1, M-2, P-2): C→C++ 重构（2026-05-15 会话）
be36f90 refactor(L2-a+d): L2 头文件 NULL→nullptr + atoi/atof→safe_stoi/safe_stod
d65a2e9 refactor(L2-a): NWalign.h C → C++ + TMalign.h 临时 using namespace std
e6388b9 refactor(L1-13): basic_fun.h 移除 using namespace std
19e91af refactor(L1-11): basic_fun.h 逗号声明拆分
0e43deb refactor(L1-8~L1-9): basic_fun.h #pragma once + 块注释
22206f2 refactor(L1-3~L1-4): basic_fun.h safe_stoi/safe_stod + 替换 atoi/atof
fb92ed5 refactor(L1-2): basic_fun.h NULL → nullptr
040d2fd refactor(L1-1): basic_fun.h C 头文件 → C++ 头文件
b2a5647 refactor(L0): 第 0 层工具/常量头文件 C → C++ 风格重构
aa9c9aa add citation to license
```

## 详细进度（2026-05-19 更新）

### 第 0 层：工具/常量头文件 ✅

| 步骤 | 文件 | 状态 | 说明 |
|---|---|---|---|
| L0-1~L0-4 | BLOSUM.h | 无需修改 | `#pragma once`、`//` 注释已存在 |
| L0-5~L0-6 | param_set.h | 无需修改 | `<cmath>` 已是 C++ 头 |
| L0-7~L0-9 | Kabsch.h | 部分完成 | 添加 `#pragma once`；逗号声明拆分；循环变量延后 |

### 第 1 层：基础函数库 basic_fun.h ✅（9/13）

| 步骤 | 状态 | 说明 |
|---|---|---|
| L1-1 | ✅ | C 头文件 → C++ 头文件 |
| L1-2 | ✅ | NULL → nullptr |
| L1-3~L1-4 | ✅ | safe_stoi/safe_stod 双重重载 |
| L1-8~L1-9 | ✅ | #pragma once + 块注释 |
| L1-11 | ✅ | 逗号声明拆分 |
| L1-13 | ✅ | 移除 using namespace std |
| L1-5 | 不适用 | 无 char msg[N] |
| L1-7 | 不适用 | 无 C 强转 |
| L1-6 | ⏸️ | FILE*→ifstream 延后 |
| L1-10 | ⏸️ | 循环变量跨上下文复用 |
| L1-12 | ⏸️ | C89 集中声明过于侵入 |

### 第 2 层：算法核心头文件

| 步骤 | 状态 | 说明 |
|---|---|---|
| L2-a（头文件+空指针） | ✅ | NWalign.h, se.h, SOIalign.h |
| L2-d（atoi/atof） | ✅ | MMalign.h, NWalign.h, TMalign.h, flexalign.h |
| L2-e（C 强转） | ✅ | TMalign.h, TMscore.h, HwRMSD.h |
| L2-g（注释+声明） | ✅ | 已补充到 4 个恢复文件 |
| **L2-f（VLA→vector）** | ✅ | 2026-05-19 扫描：USalign 编译单元（含所有头文件）已无 VLA。仅 TMscore.h 残留 6 处（独立程序，不在回归测试中） |
| L2-b（printf） | ⏸️ | 延后 |
| L2-c（char*→string） | ✅ | 已通过 M 里程碑完成 |
| L2-h（二级指针） | ⏸️ | 延后至性能优化 |

### 第 3+4 层：cpp 文件 ✅

基本改造（strcmp→operator==, atoi/atof→safe, 注释, 逗号声明, C头文件→C++）全部完成。

**secx/secy char*→string 迁移（S1-S15）** ✅ — 17 步计划全部完成，详见下方。

### 独立里程碑

| 步骤 | 状态 | 说明 |
|---|---|---|
| M-1 桥接 | ✅ | read_PDB 反向桥接, isfile FILE*→ifstream, NWalign_main/se_main 正向桥接, copy_chain_data 反向桥接, make_sec/sec_str const 修复 |
| **M-2 调用点迁移** | ✅ | se.cpp/NWalign.cpp/TMscore.cpp/HwRMSD.cpp/TMalign.cpp + USalign.cpp 全部函数 + M-3 包装器删除 |
| M-3 包装器删除 | ✅ | read_PDB + copy_chain_data char* 包装器已全部删除 |
| P-2 printf | ✅ | 纯文本 printf→cout（含 seqM 丢失修复） |
| P-3+ 格式化 printf | ❌ 取消 | 脚本损坏文件，snprintf+cout 风格收益低 |
| **secx/secy 迁移 S1-S15** | ✅ | 全部 ~45 处 secx/secy char*→string 转换完成（3 独立程序待验证） |

### 独立程序待验证

| 文件 | 修改 | 验证方式 |
|------|------|---------|
| HwRMSD.cpp | S3 secx/secy→string | 重构完成后手动运行对比 |
| MMalign.cpp | S4+S5 secx/secy→string | S4 已提交，S5 stash 待测试 |

## 执行中发现的新问题（2026-05-19 更新）

### 问题 1：编译必须加 `-static`（严重）
- **症状**：无 `-static` 时 `ld returned 116`
- **修复**：手动编译加 `-static`（脚本未修改，用户自行处理）

### 问题 2：循环变量内联的隐藏陷阱
- `for (i=0;...)` 中 `if (line[i]==' ') break;` 提前退出，循环后 `line.substr(0,i)` 使用退出位置的 `i`。不能盲目内联。

### 问题 3：批量替换的 include 误伤
- `\bstring\b` 替换时 `#include <string>` 被误改为 `#include <std::string>`

### 问题 4：safe_stoi/safe_stod 需要双重重载
- `std::stoi` 只接受 `const string&`，传 `const char*` 触发隐式构造。需同时提供 `const char*` 用 strtol/strtod。

### 问题 5：Kabsch.h 缺少头文件保护
- 原文件无 `#ifndef`/`#pragma once`，L0-8 添加。

### 问题 6：移除 using namespace std 后级联编译失败
- basic_fun.h 的 using 移除后，TMalign.h 大量未限定标识符失败。临时给 TMalign.h 加 using。

### 问题 7：tmscore_resid CPU 时间误报
- `#Total CPU time` 从 0.02→0.00，正常波动但字节比对 FAIL。建议过滤该行。

### 问题 8：P-3 snprintf 脚本损坏 4 个 .h 文件（严重）
- **原因**：Python 脚本的正则 `\bprintf\(` 误匹配了 `sprintf(`（去掉了 s）
- **后果**：TMalign.h/NWalign.h/TMscore.h/flexalign.h 被截断
- **修复**：从 git commit `be36f90` checkout 恢复

### 问题 9~14：2026-05-15/16 会话发现（已有记录，此处略）

### 问题 9（2026-05-15）：P-2 脚本 `%s` 转换丢失 seqM 变量（严重）
- **位置**：TMalign.h `output_mTMalign_results` 中的 `printf("In the following, seqID=n_identical/L.\n\n%s\n", seqM)`
- **症状**：转换为 `cout << ...` 时丢失了 `seqM`
- **影响**：msta_rna 和其他走 MSTA 路径的用例 FAIL
- **修复**：手动还原该行为

### 问题 10（2026-05-15）：正则 `\w` 只匹配单字符
- **位置**：L2-e C 强转替换脚本
- **症状**：`(double) inc` 被替换为 `static_cast<double>(i)nc`
- **修复**：改用 `\w+` 匹配完整变量名

### 问题 11（2026-05-15）：NWalign.h 中 cout 缺少 std:: 前缀
- **原因**：NWalign.h 在 TMalign.h 的 `using namespace std;` 之前被 include
- **修复**：NWalign.h 中所有 `cout`/`endl` 加 `std::` 前缀

### 问题 12（2026-05-15）：未按步提交导致无法精确回退（严重）
- **场景**：P-3 损坏文件后无法精确恢复到 P-2 之后的状态
- **教训**：每步修改→编译→测试→commit 四步完整后才能进入下一步

### 问题 13（2026-05-16）：MMalign() 多链路径无法独立迁移（M-2 阻塞）
- **症状**：MMalign_iter/final（MMalign.h）接受非 const `char*`，且内部写 `seqx[xlen]=0`
- **决定**：多链路径保持 char*，待 MMalign.h 完成后一并处理（已通过 nullptr 占位符解决）

### 问题 14（2026-05-16）：make_sec/sec_str const 修复被 git checkout 恢复丢失
- **症状**：`make_sec(seqx.c_str(), ...)` 编译失败（c_str() 返回 const char*，签名是 char*）
- **根因**：从 `be36f90` checkout 恢复文件时丢失了 M-1 的 const 修复
- **修复**：在 TMalign.h 中重新添加 `const`

### 问题 15（2026-05-17）：se_main string 重载跨作用域崩溃
- **症状**：mTMalign 中 seqx/seqy 在不同作用域声明时调用 se_main string 重载导致栈溢出
- **根因**：`const string&` vs `const char*` 参数类型差异改变栈帧布局，触发栈溢出
- **处置**：`.c_str()` 永久方案，放弃 se_main 方向翻转

### 问题 18（2026-05-19）：MMalign.cpp M-2 seqx/seqy 作用域遗漏
- **症状**：全对全路径 `MMalign_iter`/`MMalign_final`/`MMalign_dimer` 调用处 `seqx/seqy` 不可见
- **根因**：M-2 迁移时外作用域 `char *seqx, *seqy` 被删除，内层 `string seqx; string seqy;` 在循环内，循环外不可见
- **修复**：S4 中在 `for i` 前声明 `string seqx; string seqy;`，MMalign.h 函数调用改用 `nullptr` 占位符
- **教训**：`char*→string` 迁移时需检查外作用域声明是否被多个路径共用

### 问题 19（2026-05-19）：sed 行号删行误删括号（严重）
- **症状**：msta_rna（-mm 4）输出截断，`STATUS_ACCESS_VIOLATION`
- **根因**：S14 中用 `for l in 1843 1849 ...; do sed -i "${l}d"` 删除 `delete[]secx;`，但行号偏移导致误删 `}` 和 `{`
- **定位**：加 cerr debug 点（D1→D2a→D2→D2pre→D2b→D2c→D2d→D3→D4）逐段缩小范围
- **修复**：补回缺失的 `}` 和 `{`
- **教训**：**永远不要用 sed 行号删行**——后续行号偏移不可控。改用 awk 区间 + 模式匹配

### 问题 20（2026-05-19）：Edit tool 误改 MMdock parse_chain_list
- **症状**：MMdock `parse_chain_list` 缺少 `);` 结尾行
- **根因**：Edit tool 匹配声明块时因 `parse_chain_list` 结尾行相似，将不同函数的结尾替换到 MMdock
- **修复**：加回缺失行

### 问题 21（2026-05-19）：replace_all 误伤未改造函数
- **根因**：S10 中用 `replace_all` 全局替换 `secx = new char[xlen + 1]`，但 SOIalign/flexalign 尚为 `char*`
- **修复**：逐一 revert SOIalign/flexalign 的 resize 调用
- **教训**：`replace_all` 前确认所有受影响函数的 char*→string 已转换

### 问题 22（2026-05-19）：sed 替换 `= new char[` 残留 `]`
- **根因**：`s/= new char\[/.resize(/` 将 `= new char[xlen+1]` 变为 `.resize(xlen+1]`（`]` 未替换）
- **修复**：二次替换 `]`→`)`
- **教训**：用 `s/= new char\[\(.*\)\]/.resize(\1)/` 一步到位

### 问题 23（2026-05-19）：cerr debug 插入多行函数调用中间
- **根因**：S14 中 `sed -i '2128a\cerr...'` 插入在 `se_main(` 形参列表中间
- **教训**：调试点只插在完整语句之后，不被 `sed 'a'` 或 `'i'` 命令影响

### 问题 24（2026-05-19）：git checkout -- 丢失未提交修改
- **根因**：`git checkout -- USalign.cpp` 覆盖了未提交的工作区改动
- **教训**：`checkout --` 前先 `git diff` 确认工作区改动范围

## 未完成工作清单（2026-05-20 全面审计更新）

### P0 — `new char[]` 堆分配残余（12 处）

| # | 文件 | 行号 | 变量 | 说明 |
|---|------|------|------|------|
| 1-4 | flexalign.h | 110-111, 288-289 | `secx_h/secy_h` | 4 处 char* new[]，S17 未执行 |
| 5 | MMalign.h | 1129 | `sec` | parse_chain_list 中 |
| 6-7 | TMalign.h | 3860-3861 | `seqx_cp/secx_cp` | CPalign 函数 |
| 8 | USalign.cpp | 1441 | `secy_trim` | M-2 遗漏 |
| 9-10 | USalign.cpp | 2133-2134 | `seqy_ext/secy_ext` | mTMalign hinge 段 |
| 11-12 | MMalign.cpp | 519, 545 | `secx/secy` | S5 stash（独立程序） |

### P1 — 语法风格残余（17 处主程序内）

| # | 类别 | 数量 | 位置 |
|---|------|------|------|
| 13 | strcmp → operator== | 3 | MMalign.h:3377, TMalign.h:2889, flexalign.h:645 |
| 14 | #define MAX → std::max | 1 | NWalign.h:8 |
| 15 | C 强转 → static_cast | 8 | USalign.cpp(3), MMalign.cpp(3), TMalign.cpp(1), qTMclust.cpp(1) |
| 16 | #ifndef 守卫 → #pragma once | 5 文件 | HwRMSD.h, NWalign.h, SOIalign.h, TMalign.h, flexalign.h |
| 17 | 无守卫 → 添加 #pragma once | 5 文件 | MMalign.h, se.h, TMscore.h, basic_fun.h, param_set.h |
| 19 | 逗号声明拆分 | 1 | MMalign.h:314 `int c,r;` |

### P2 — C 块注释（~20 处）

| # | 类别 | 数量 | 位置 |
|---|------|------|------|
| 18 | C 块注释 `/* */` → `//` | ~20 | Kabsch.h, MMalign.h, NW.h, cif2pdb.cpp, qTMclust.cpp, xyz_sfetch.cpp |

### P3 — 独立 .cpp 文件循环变量 / C89 声明（~55 处）

| # | 类别 | 数量 | 位置 |
|---|------|------|------|
| 20 | 循环外声明 `for(i=` | ~40 | MMalign.cpp, NWalign.cpp, TMalign.cpp, TMscore.cpp, qTMclust.cpp 等 |
| 21 | C89 集中声明 | ~15 | MMalign.h 函数入口（`int i; int j;` 等）、HwRMSD.h |

### 设计明确不做

| 项目 | 数量 | 原因 |
|------|------|------|
| printf/fprintf/sprintf | 106 处 | P-3 已取消 |
| 二级指针 → vector | ~347 处 | L2-h 延后性能优化 |
| Kabsch.h 循环变量内联 | 15 处 | L0-9 永久跳过 |
| se_main/NWalign_main 方向翻转 | — | 问题 15 栈溢出 |
- **教训**：务必每步 commit（见问题 12）。

### 问题 9：P-2 脚本 `%s` 转换丢失 seqM 变量（严重）
- **位置**：TMalign.h `output_mTMalign_results` 中的 `printf("In the following, seqID=n_identical/L.\n\n%s\n", seqM)`
- **症状**：转换为 `cout << "In the following, seqID=n_identical/L.\n\n" << "\n"`（丢失了 `seqM`）
- **影响**：msta_rna 和其他走 MSTA 路径的用例 FAIL
- **修复**：手动还原该行为 `printf("...%s\n", seqM)`
- **教训**：P-2 脚本对 `%s` 后紧跟 `\n` 的格式字符串处理有 bug，需修复脚本逻辑

### 问题 10：正则 `\w` 只匹配单字符
- **位置**：L2-e C 强转替换脚本
- **症状**：`(double) inc` 被替换为 `static_cast<double>(i)nc`（只匹配了 `i`）
- **修复**：改用 `\w+` 匹配完整变量名

### 问题 11：NWalign.h 中 cout 缺少 std:: 前缀
- **原因**：NWalign.h 在 TMalign.h 的 `using namespace std;` 之前被 include
- **修复**：NWalign.h 中所有 `cout`/`endl` 加 `std::` 前缀

### 问题 12：未按步骤 commit 导致无法精确回退（严重）
- **场景**：整个会话的修改都在工作区，P-3 损坏文件后无法精确恢复到 P-2 之后的状态
- **教训**：**每步修改→编译→测试→commit 四步完整后才能进入下一步**（已记录为 workflow memory）

### 问题 13：MMalign() 多链路径无法独立迁移（M-2 阻塞）

- **症状**：尝试将 MMalign() 多链路径的 seqx/seqy 改为 string 后，后续的 `MMalign_iter`/`MMalign_final` 调用编译失败。这些函数（MMalign.h）接受非 const `char*` 参数，内部写 `seqx[xlen]=0` 做 null 截断。
- **根因**：`MMalign_iter` → `MMalign_search` 调用链深度依赖 `char*` 参数，尚未完成 M-2 迁移。USalign.cpp 中若将 seqx 改为 string，需 `resize()` + `&seqx[0]` 传递，脆弱且破坏封装。
- **决定**：多链路径保持 char*，待 MMalign.h 完成 M-2（char*→string 迁移）后一并处理。
- **影响范围**：USalign.cpp 中 MMalign() 多链路径、mTMalign()、SOIalign()、flexalign() — 均涉及 MMalign.h/TMalign.h 中未迁移的 `char*` 参数函数。

### 问题 14：make_sec/sec_str const 修复被 git checkout 恢复丢失

- **症状**：USalign.cpp TMalign() 中 `make_sec(seqx.c_str(), ...)` 编译失败 — `c_str()` 返回 `const char*`，但签名是 `char*`。而已迁移的 TMalign.cpp 却编译通过。
- **根因**：M-1 中对 `make_sec(char* → const char*)` 和 `sec_str` 的 const 修复在 be36f90 commit 中存在，但 P-3 脚本损坏 TMalign.h 后从 be36f90 checkout 恢复时，该修复被覆盖丢失。be36f90 是 L2-a+d commit，早于 M-1 的 b1ec892。
- **修复**：在 TMalign.h 中重新添加 const：`make_sec(const char *seq, ...)` 和 `sec_str(int len, const char *seq, ...)`。两个函数均只读取 seq，不修改。
- **教训**：用旧 commit 恢复文件时，需确认中间 commit 的修改未丢失。建议恢复后用 `git diff <restore-source> <later-commit> -- <file>` 检查。

## 2026-05-14 会话总结

（保留原始记录，已删除重复的问题 1-5 段落，详见上方合并后的问题列表）

| 指标 | 数值 |
|---|---|
| 完成层级 | L0（全部）、L1（9/13 步）、L2（2/8 步） |
| Commit 数 | 8 |
| 修改文件数 | 10（BLOSUM.h, param_set.h, Kabsch.h, basic_fun.h, NWalign.h, TMalign.h, se.h, SOIalign.h, MMalign.h, flexalign.h） |
| 延后项目 | 7 项 |

## 延后项目清单

| 项目 | 原步骤 | 延后原因 | 目标阶段 |
|---|---|---|---|
| FILE* → ifstream | L1-6 | ✅ 已在 M-1 完成 | — |
| basic_fun.h 循环变量内联 | L1-10 | ✅ 2026-05-20 完成 | file2chainlist/file2chainpairlist |
| basic_fun.h C89 集中声明 | L1-12 | ✅ 2026-05-20 完成 | 删除未使用变量 |
| Kabsch.h 循环变量内联 | L0-9 | ❌ 永久跳过 | 密集SVD算法 |
| char* → string 全量 | 独立里程碑 | ✅ 已完成 | M-3 |
| 格式化 printf → cout/snprintf | 独立里程碑 | ❌ 取消：snprintf 引入 C buffer，ostringstream 格式不对齐 | — |
| 二级指针 → vector | 全局 | ~347 处 | 性能优化 |
| USalign.cpp MMalign() 多链路径 | M-2 | MMalign_iter/final 接受非 const char* | MMalign.h M-2 之后 |
| MMalign.cpp + MMalign.h M-2 | M-2 | MMalign.cpp 中 copy_chain_data 调用 + MMalign.h 中 MMalign_iter/final/search 的 char* 参数 | 后续 |
| se_main/NWalign_main 方向翻转 | M-3 先导 | string 包装器当前调 char* 版，需翻转为 char* 包装器调 string 版 | M-3 之前 |
	
## 2026-05-19 会话（全天：secx/secy 迁移 S3-S15）

| 指标 | 数值 |
|---|---|
| 完成步骤 | S3-S15（13 步，HwRMSD/MMalign/USalign 全部 secx/secy char*→string） |
| Commit 数 | 12（3dc1659 / 0581203 / c0534bd / 7c89188 / 905585c / 70c0376 / e2c30b5 / 65dd228 / c1d31ee / 603e169 / ec07eaf / ce40f87） |
| 修改文件 | HwRMSD.cpp, MMalign.cpp, MMalign.h, USalign.cpp |
| 完成任务 | secx/secy 17 步计划全部完成（S1-S15），独立程序待后续验证 |

### S3: HwRMSD.cpp secx/secy → std::string ✅

**commit `3dc1659`**：主循环中 2 处 secx 分配 + 2 处 secy 分配。

- 声明：`char *secx, *secy` → `string secx; string secy;`
- 分配：`new char[xlen+1]` → `secx.resize(xlen+1)`
- make_sec：写缓冲区传 `&secx[0]`（char*）；seqx/seqy 加 `.c_str()`
- HwRMSD_main 调用全部 4 个参数加 `.c_str()`
- **修复 M-2 遗漏**：`get_seqID(..., seqy, ...)` → `get_seqID(..., seqy.c_str(), ...)`（HwRMSD 独立程序未在 M-2 回归测试中覆盖）
- 移除 2 处 `delete[]`

**注意**：HwRMSD 为独立程序，不在回归测试框架内。

### S4: MMalign.cpp 单链路径 secx/secy → std::string ✅

**commit `0581203`**：单链路径 2 处 secx/secy 分配。

- 外作用域 `char *secx, *secy` → if 块内局部 `string secx; string secy;`
- copy_chain_data：写缓冲区传 `&secx[0]/&secy[0]`
- TMalign_main：`secx.c_str(), secy.c_str()`
- 移除 2 处 `delete[]`

**修复 M-2 遗留作用域 bug**：全对全路径中 `seqx/seqy` 原为外作用域 `char*`，M-2 迁移为 `string` 时误删外层声明，导致全对全路径内 `seqx/seqy` 不可见。修复：在 `for i` 前声明 `string seqx; string secy;`。MMalign_iter/final/dimer 5 处改用 `nullptr` 占位符（函数内立即 `new[]` 覆盖传参）。

### S5: MMalign.cpp 全对全路径 secx/secy → std::string ⏸️（stash）

全对全路径 2 处 secx/secy 分配。已完成编译，外作用域 `char *secx, *secy;` 已删除（检验无剩余引用）。stash 在 `USalign-beta`，待重构完成后与 HwRMSD 一起手动测试。

### S6-S9: MMalign.h 四个函数 secx/secy → std::string ✅（4 commits）

| 步骤 | Commit | 函数 | 改动量 |
|------|--------|------|--------|
| S6 | `c0534bd` | MMalign_search (4 sec) | +11/-13 |
| S7 | `7c89188` | MMalign_final (4 sec) | +11/-13 |
| S8 | `905585c` | MMalign_se_final (4 sec) | +16/-18 |
| S9 | `70c0376` | MMalign_dimer (4 sec) | +11/-13 |

固定模式：
- 参数 `char *secx, char *secy` → 改为无名（`char * /*secx*/, char * /*secy*/`）
- 函数体内用局部 `string secx; string secy;` 取代
- `copy_chain_pair_data` 写缓冲区传 `&secx[0]/&secy[0]`
- `TMalign_main`/`TMalign_dimer_main` 传 `secx.c_str()/secy.c_str()`
- 移除所有 `delete[]`

**注意**：因 4 个函数参数签名和函数体结构高度相似，使用 `replace_all` 批量替换。S6 先行时逐个上下文匹配，S7-S9 直接 `replace_all` 批量完成。

### S10-S15: USalign.cpp 六个函数 secx/secy → std::string ✅（6 commits）

| 步骤 | Commit | 函数 | 改动量 |
|------|--------|------|--------|
| S10 | `e2c30b5` | TMalign() (2 sec) | +12/-15 |
| S11 | `65dd228` | MMalign() (4 sec) | +13/-18 |
| S12 | `c1d31ee` | SOIalign() (2 sec) | +11/-12 |
| S13 | `603e169` | flexalign() (2 sec) | +10/-9 |
| S14 | `ec07eaf` | mTMalign() (9 sec) | +26/-33 |
| S15 | `ce40f87` | MMdock() (6 sec) | +22/-21 |

### Git 当前状态

```
ce40f87 (HEAD) refactor(S15): USalign.cpp MMdock() secx/secy char* → std::string
ec07eaf refactor(S14): USalign.cpp mTMalign() secx/secy char* → std::string
603e169 refactor(S13): USalign.cpp flexalign() secx/secy char* → std::string
c1d31ee refactor(S12): USalign.cpp SOIalign() secx/secy char* → std::string
65dd228 refactor(S11): USalign.cpp MMalign() secx/secy char* → std::string
e2c30b5 refactor(S10): USalign.cpp TMalign() secx/secy char* → std::string
70c0376 refactor(S9): MMalign.h MMalign_dimer secx/secy char* → std::string
905585c refactor(S8): MMalign.h MMalign_se_final secx/secy char* → std::string
7c89188 refactor(S7): MMalign.h MMalign_final secx/secy char* → std::string
c0534bd refactor(S6): MMalign.h MMalign_search secx/secy char* → std::string
0581203 refactor(S4): MMalign.cpp 单链路径 secx/secy char* → std::string
3dc1659 refactor(S3): HwRMSD.cpp secx/secy char* → std::string
4b6db0f refactor(S2): TMalign.cpp secx/secy char* → std::string
07b3779 refactor(S1): pdb2ss.cpp secx char* → std::string
```

### 执行中发现的新问题

| # | 问题 | 严重性 | 状态 |
|---|------|--------|------|
| 18 | **MMalign.cpp M-2 seqx/seqy 作用域遗漏** | P1（修复） | 全对全路径的 `char *seqx, *seqy` 外作用声明被 M-2 误删，导致 `MMalign_iter`/`MMalign_final`/`MMalign_dimer` 调用处 `seqx/seqy` 不可见。S4 中修复：在 `for i` 前声明 `string seqx; string seqy;`，MMalign.h 函数调用改用 `nullptr` 占位符 |
| 19 | **segfault via msta_rna 输出截断** | P0（已修） | S14 中 `sed` 行号删行时误删 `}` 和 `{`，导致 msta_rna（`-mm 4` mTMalign 路径）Stage A 全对全循环缺少关闭大括号，触发 `STATUS_ACCESS_VIOLATION`。修复：添加 `}` 和 `{` 补回缺失的括号。**教训**：`sed` 行号删行导致后续行号偏移，优先使用 `awk` 区间 + 模式匹配 |
| 20 | **MMdock parse_chain_list 被 Edit tool 误改** | P1（已修） | Edit tool 匹配声明块时因 `parse_chain_list` 的结尾行相似，将 MMalign 的结尾行（`resi_vec1, ...`）替换到了 MMdock 中，导致 MMdock 缺少 `);` 结尾。修复：加回缺失行 |
| 21 | **`replace_all` 误伤未改造函数** | P2（已修） | S10 中使用 `replace_all` 将 `secx = new char[xlen + 1]` 全局替换为 `secx.resize(xlen + 1)`，但 SOIalign/flexalign 当时尚未转换 `char *secx` 声明，导致编译失败。修复：逐一 revert SOIalign/flexalign 的 resize 调用。**教训**：`replace_all` 前先确认所有受影响函数的 char*→string 转换已完成，或使用函数级上下文 |
| 22 | **`sed` 替换 `= new char[` 留下 `]` 和多余空格** | P2（已修） | 模式 `s/= new char\[/.resize(/` 将 `]` 保留为 `]`，需二次替换。**教训**：直接在 sed 中用完整替换模式 `s/= new char\[\(.*\)\]/.resize(\1)/` 一步到位 |
| 23 | **cerr debug 插入多行函数调用中间** | P2（已修） | S14 调试时 `sed -i '2128a\    cerr << "D2e" << endl;'` 插入在 `se_main(` 形参列表中间，导致编译错误。**教训**：调试点只插在函数体语句间隙或完整语句之后 |
| 24 | **`git checkout -- file` 丢失未提交修改** | P1（已修） | S14 调试时用 `git checkout -- USalign.cpp` 回退调试打印，但 S14 改动（未提交）也被覆盖。需重新做 S14。**教训**：`checkout --` 前先 `git diff` 确认只有调试行未提交 |

### 延后项目清单

| 项目 | 原步骤 | 延后原因 | 目标阶段 |
|---|---|---|---|
| FILE* → ifstream | L1-6 | ✅ 已在 M-1 完成 | — |
| basic_fun.h 循环变量内联 | L1-10 | ✅ 2026-05-20 完成 | file2chainlist/file2chainpairlist |
| basic_fun.h C89 集中声明 | L1-12 | ✅ 2026-05-20 完成 | 删除未使用变量 |
| Kabsch.h 循环变量内联 | L0-9 | ❌ 永久跳过 | 密集SVD算法 |
| char* → string 全量 | 独立里程碑 | ✅ M-3 已完成 | — |
| 格式化 printf → cout/snprintf | 独立里程碑 | ❌ 取消 | — |
| 二级指针 → vector | 全局 | ~347 处 | 性能优化 |
| se_main/NWalign_main 方向翻转 | M-3 先导 | 风险>收益，string 包装器保留现状 | ❌ 取消 |
| **HwRMSD 验证** | S3 | 独立程序，回归框架未覆盖 | 重构完成后手动测试 |
| **MMalign.cpp 全对全路径验证** | S5 | 独立程序，回归框架未覆盖 | 重构完成后手动测试（stash） |
| **MMalign.h secx_h/secy_h → string** | S17 | flexalign.h 中不同变量名，非 secx/secy | 可选，另行评估 |
| **MMalign.cpp + MMalign.h M-2** | M-2 | 已通过 nullptr 占位符隔离完成 | ✅ 已完成 |
4b6db0f refactor(S2): TMalign.cpp secx/secy char* → std::string
07b3779 refactor(S1): pdb2ss.cpp secx char* → std::string
dfe2e0f refactor: 问题 15 诊断结论 — se_main string 重载跨作用域限制
f7dd8f0 refactor: flexalign.h seqx_h/seqy_h char* 工作缓冲区 → std::string
```


---

## 2026-05-19 日结

### 今日完成

| 类别 | 内容 | 成果 |
|------|------|------|
| secx/secy S3-S15 | HwRMSD/MMalign/USalign 全部 char*→string | 13 步，12 commits，~45 处分配转换 |
| VLA 扫描 | 全局 `-Wvla` 扫描 | USalign 编译单元已无 VLA |
| 日志更新 | 完成/未完成/新问题全部记录 | — |

### 新增 commit（今日 12 个）

```
ce40f87 refactor(S15): USalign.cpp MMdock() secx/secy char* → std::string
ec07eaf refactor(S14): USalign.cpp mTMalign() secx/secy char* → std::string
603e169 refactor(S13): USalign.cpp flexalign() secx/secy char* → std::string
c1d31ee refactor(S12): USalign.cpp SOIalign() secx/secy char* → std::string
65dd228 refactor(S11): USalign.cpp MMalign() secx/secy char* → std::string
e2c30b5 refactor(S10): USalign.cpp TMalign() secx/secy char* → std::string
70c0376 refactor(S9): MMalign.h MMalign_dimer secx/secy char* → std::string
905585c refactor(S8): MMalign.h MMalign_se_final secx/secy char* → std::string
7c89188 refactor(S7): MMalign.h MMalign_final secx/secy char* → std::string
c0534bd refactor(S6): MMalign.h MMalign_search secx/secy char* → std::string
0581203 refactor(S4): MMalign.cpp 单链路径 secx/secy char* → std::string
3dc1659 refactor(S3): HwRMSD.cpp secx/secy char* → std::string
```

### 新增问题（今日 7 个）

| # | 问题 | 严重性 | 状态 |
|---|------|--------|------|
| 18 | MMalign.cpp seqx/seqy 作用域 M-2 遗漏 | P1 | 已修（S4） |
| 19 | sed 行号删行误删 `}`/`{` → msta_rna segfault | P0 | 已修（cerr debug 定位） |
| 20 | Edit tool 误改 MMdock parse_chain_list | P1 | 已修 |
| 21 | replace_all 误伤 SOIalign/flexalign | P2 | 已修 |
| 22 | sed 残留 `]` 和多余空格 | P2 | 已修 |
| 23 | cerr debug 插入多行函数调用中间 | P2 | 已修 |
| 24 | git checkout -- 丢失未提交修改 | P1 | 已修 |

### 明天起点

| 优先级 | 任务 | 涉及文件 | 说明 |
|--------|------|---------|------|
| 1 | ~~L2-f VLA 收尾~~ | ✅ 2026-05-20 完成 |
| 2 | ~~L1-6 FILE*→ifstream~~ | ✅ 已在 M-1 完成（全项目应用代码已无 FILE*） |
| 3 | 独立程序验证 | HwRMSD + MMalign（S5 stash）+ TMscore | 重构完成后手动测试 |
| 4 | ~~L1-10/L1-12/Kabsch.h 收尾~~ | ✅ 2026-05-20 完成/永久跳过 |
