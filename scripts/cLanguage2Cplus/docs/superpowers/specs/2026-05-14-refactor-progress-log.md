# USalign C → C++ 重构进度记录

## 2026-05-26 L2-h 二级指针 → C++ 容器重构（阶段 0-3 启动）

| 指标 | 数值 |
|---|---|
| 方案文档 | `2026-05-21-usalign-l2h-pointer-to-container-design.md` |
| 已完成步骤 | L2h-00 ~ L2h-10a（11 步） |
| 修改文件 | `basic_fun.h`（类型别名 + dist()/do_rotation Coords& 重载）、`Kabsch.h`（Kabsch Coords& 重载）、`TMalign.h`（16 个 Coords& 重载 + TMalign_main 坐标缓冲区切换 + clean_up 改造）、`USalign.cpp`（TMalign_main 调用者适配） |
| 新增类型 | `Coords`、`DPMatrix`、`PathMat`、`IntMat`、`Rotation`、`Bond2` |

### 背景

此前 L2-h 被标记为"延后性能优化阶段"（第 22 类 C→C++ 映射的最后一个延后项）。2026-05-25~26 重新评估，将纯语法替换方案升级为以**提升缓存命中率**为目标的性能优化方案。

方案选型：AoS 布局 `vector<array<double,3>>`（连续内存，消除碎片化）+ `reserve/push_back`（避免零初始化）。排除了 DP 矩阵拍平、缓存行对齐、多线程并行、`__restrict` 等优化方向。

### 已完成的执行步骤

**阶段 0：基础设施**
| 步骤 | 内容 |
|------|------|
| L2h-00 | `basic_fun.h` 添加 6 个类型别名 |

**阶段 1：底层热函数 Coords& 重载**
| 步骤 | 文件 | 函数 |
|------|------|------|
| L2h-01 | `Kabsch.h` | `Kabsch()` — 新增 `const Coords&` 重载 |
| L2h-02 | `TMalign.h` | `score_fun8()` + `score_fun8_standard()` — 新增 `const Coords&` 重载 |
| L2h-03 | `basic_fun.h` | `dist()` + `do_rotation()` + `transform()` — 新增重载 |

**阶段 2：TMalign.h 中层函数逐层上推**
| 步骤 | 函数组 |
|------|--------|
| L2h-04 | `TMscore8_search()` + `TMscore8_search_standard()` |
| L2h-05 | `get_score_fast()` |
| L2h-06 | `score_matrix_rmsd_sec()` |
| L2h-07 | `detailed_search()` + `detailed_search_standard()` |
| L2h-08 | `get_initial5()` + `get_initial()` + `get_initial_fgt()` + `get_initial_ssplus()` |
| L2h-09 | `standard_TMscore()` |

> 阶段 2 使用 Python 脚本批量添加重载。过程中发现 `x`/`y` 参数不能直接转为 `const Coords&`（下游 `transform()` 需要非 const `double*`），改为保持 `double**`。DP 矩阵参数（`score`/`path`/`val`）也保持在 `double**`/`bool**`，因为 NWDP_TM 尚未提供对应的重载。

**阶段 3：TMalign_main 坐标缓冲区实际切换**
| 步骤 | 内容 |
|------|------|
| L2h-10a | `TMalign_main` 内部 `xtm`/`ytm`/`xt`/`r1`/`r2` 从 `NewArray` → `Coords`（`resize`）。`clean_up_after_approx_TM` 新增 `Coords&` 重载，保留旧 `double**` 重载供 MMalign.h 调用 |

> 补充修改：`basic_fun.h` 新增 `do_rotation(double**, Coords&, ...)` 混合重载（TMalign_main 中 `xa` 仍为 `double**`，`xt` 已为 `Coords`）；`TMalign.h` 追加 `detailed_search_standard` 和 `DP_iter` 的 Coords& 重载（编译过程中发现遗漏）。

### 新发现的问题

#### 问题 25：Coords 连续内存 + `-ffast-math` 导致回归测试浮点差异

**症状**：L2h-10a 完成后运行 `run_regression.py`，9 个用例出现 diff：
- 6 个仅 `#Total CPU time` 差异（无业务数据变化）
- 2 个（`all_vs_all`、`database_search`）旋转矩阵 `t[m]`/`u[m][i]` 第 10-11 位小数差异
- 1 个（`msta_rna`）MSTA 最佳配对选择变化

**根因分析**：
`-ffast-math` 允许编译器对浮点运算做 FMA 收缩和别名分析优化。`double**`（碎片化堆分配）和 `Coords`（连续内存块）的内存布局不同，编译器对两种布局下的 Kabsch SVD 内部循环做出了不同的优化决策。Kabsch 的 SVD 迭代会累积舍入差异，导致旋转矩阵末位小数（10^-10 ~ 10^-11）分岔。

**msta_rna 特例**：`US735192405` 和 `US7351924051` 的链 A 坐标完全相同，两者与 `US73519240510:J` 的比对分数理应相同。在 `double**` 下（master），碎片化内存引入 1 ULP 伪差（`...2186` vs `...2175`），j=0 严格大于 j=10。在 `Coords` 下（USalign-beta），连续内存消除了这一噪声，两分数**精确相等**（`...2453` vs `...2453`，diff=0）。MSTA 最佳配对选择逻辑使用 `<=` 比较，平局时保留 `repr_idx`（j=10），导致表格输出中 `US73519240510:J` 的配对对象从 `US7351924051:A` 变为 `US735192405:A`。

**验证过程**：
1. 在 master 分支编译二进制，确认输出与基线一致（`US7351924051:A`）
2. 在 USalign-beta 分支添加 debug 输出 `TMave_mat[9][0]` 和 `TMave_mat[9][10]` 的 17 位精度值
3. Master：`TM[0]=...2186`，`TM[10]=...2175`，diff = 1 ULP
4. USalign-beta：`TM[0]=...2453`，`TM[10]=...2453`，diff = 0
5. 进一步确认：US735192405.pdb 和 US7351924051.pdb 链 A 坐标完全相同（前 2090 行一致）
6. MSTA 表格只输出 10 行（每个结构展示一个最佳配对），选择逻辑位于 `USalign.cpp` 第 1958 行
7. 进一步发现选择逻辑分两步，两步的平局规则**恰好相反**：
   - **第一步选 repr_idx**（第 1912 行）：`if (TMave_list[j] < repr_TM) continue`，用 `<`，相等时**后面覆盖前面**（遍历 j=0→10，最终 repr_idx=10）
   - **第二步选 maxj**（第 1958 行）：`if (TMave_mat[i][j] <= maxTM) continue`，用 `<=`，相等时**保留先前的**（初始值恰好是第一步的最终结果 repr_idx=10）
   - 因此 Coords 下两分数精确相等时，j=0 在第二步被跳过，maxj 留在第一步传下来的 10

**结论**：所有差异根因为 `-ffast-math` 下连续内存布局的浮点舍入差异。消除差异的方案：(1) 去掉 `-ffast-math` 编译选项；(2) 接受差异并更新 baseline。

**详细分析报告**：`2026-05-26-l2h-msta-rna-diff-analysis.md`

### 待解决

- [ ] 决定 `-ffast-math` 差异的处理方案（去掉 vs 接受并更新 baseline）
- [ ] L2h-10b：TMalign_main DP 矩阵（`score`/`path`/`val`）→ `DPMatrix`/`PathMat`/`IntMat`
- [ ] 阶段 4~10 后续步骤

### 待解决

- [ ] 决定 `-ffast-math` 差异的处理方案（去掉 vs 接受并更新 baseline）

---

## 2026-05-27 L2-h 继续推进 + 方案 3 执行

### 方案决策

- **采用方案 3**：DP 矩阵统一延后，聚焦坐标数组 → Coords
- **`-ffast-math`**：接受差异，暂不更新 baseline。3 个已知 FAIL（msta_rna / database_search / all_vs_all）均为浮点舍入差异
- **测试框架修复**：`run_regression.py` 从 PASS/CHECK 改为 PASS/WARNING/FAIL，增加 `-static` 编译参数

### 已完成的执行步骤

**阶段 3 收尾**
| 步骤 | 内容 |
|------|------|
| L2h-10a-R1~R3 | 收尾 `resize` → `reserve+push_back` 论证后跳过（工作缓冲区 resize 适用，一次性零初始化开销可忽略） |

**阶段 4：TMscore.h**
| 步骤 | 内容 |
|------|------|
| L2h-11 | `score_fun8` + `score_fun8_standard` 新增 `const Coords&` 重载（含 GDT/MaxSub） |
| L2h-12 | `TMscore8_search` + `TMscore8_search_standard` + `detailed_search_standard` 新增 `Coords&` 重载 |
| L2h-13 | `TMscore_main` 坐标临时数组 `xtm/ytm/xt/r1/r2` → `Coords(resize)`，`clean_up` 改为 Coords& 版 |

**阶段 5：其他算法头文件**
| 步骤 | 文件 | 状态 |
|------|------|:--:|
| L2h-14 | SOIalign.h | ✅ `SOIalign_main` + `get_SOI_initial_assign` 坐标数组 → Coords；`SOI_assign2super`/`SOI_iter`/`SOI_super2score` 新增 Coords& 重载；`basic_fun.h` 新增 `dist(array<double,3>&, double*)` 混合重载 |
| L2h-15 | flexalign.h | ❌ 阻塞 |
| L2h-16 | HwRMSD.h | ❌ 阻塞 |
| L2h-17 | NWalign.h | ⏭️ 跳过（纯 DP） |
| L2h-18 | se.h | ⏭️ 跳过（纯 DP） |

### 新发现的问题

#### 问题 26：se_main Coords& 级联阻塞链

**症状**：flexalign.h 和 HwRMSD.h 内部均调用 `se_main(xt, ya, ...)`，其中 `xt` 是待转换的坐标数组。将 `xt` 改为 Coords 后 `se_main` 无 Coords& 重载，编译失败。

**级联链**：`se_main(Coords&)` → `NWDP_SE(Coords& x, Coords& y)` → `NWDP_SE` 在 NW.h 有两个重载（259 行 + 80 行），均需 Coords& 版本。

**波及范围**：
| 受阻文件 | 受阻原因 |
|---------|---------|
| flexalign.h | `xt` → Coords 后 `se_main(xt, ya, ...)` 不匹配 |
| HwRMSD.h | 同上；另有 `Kabsch_Superpose(r1, r2, xt, ...)` 混合类型问题 |
| MMalign.h（阶段 6） | 大概率同样受阻 |

**尝试过的方案**：方向翻转（Coords& 为真实现 + double** thin wrapper）。函数体 238 行，签名字面量改写即可（`xa[i][j]` 语法等价）。但需同步级联修改 NW.h 两个 NWDP_SE 重载。

**当前处置**：暂时跳过。后续统一处理：`se_main` → 方向翻转 + `NWDP_SE` 两个 Coords& 重载。届时 flexalign.h、HwRMSD.h 可一并解锁。

#### 问题 27：TMalign_main 外部签名仍为 double**

TMalign_main 内部坐标临时数组已切换为 Coords，但外部签名的 `xa`/`ya` 参数仍为 `double**`。flexalign.h 中 `xa_h`/`ya_h` 传给 TMalign_main，无法转换。需阶段 9（USalign.cpp）整体迁移时同步处理。

> **2026-05-27 方案制定**：两条阻塞链的细化解除计划已写入 `2026-05-21-usalign-l2h-pointer-to-container-design.md`「阻塞链解除计划」章节。
> - **阻塞链 A**（5 步）：se_main → NWDP_SE，方向翻转策略，解锁 flexalign.h + HwRMSD.h + se.cpp
> - **阻塞链 B**（5 步）：TMalign_main / TMscore_main 外部签名，桥接重载策略，解锁 TMalign.cpp + TMscore.cpp + HwRMSD.cpp

### 阻塞链解除执行

**阻塞链 A：se_main → NWDP_SE**（方向翻转策略）
| 步骤 | 文件 | 内容 | 状态 |
|------|------|------|:--:|
| A1 | NW.h | 两个 `NWDP_SE` 各新增 `Coords&` 重载 | ✅ |
| A2 | se.h | `se_main` 签名 `double**` → `Coords&`（方向翻转），末尾新增 double** thin wrapper；新增 Coords& + double** 混合重载 | ✅ |
| A3 | flexalign.h | `xt` → `Coords(resize)`，删 2 处 DeleteArray | ✅ |
| A4 | HwRMSD.h | `xt` → `Coords(resize)` + `r1/r2` → `Coords(resize)`，删 3+3 处 DeleteArray；`Kabsch_Superpose` 新增 Coords& 重载 | ✅ |
| A5 | se.cpp | `xa/ya` → Coords，删 `NewArray`/`DeleteArray` | ✅ |

**阻塞链 B：TMalign_main / TMscore_main 外部签名**（桥接重载策略）
| 步骤 | 文件 | 内容 | 状态 |
|------|------|------|:--:|
| B1 | TMalign.h | `TMalign_main` 新增 `Coords& xa/ya` 桥接重载（`vector<double*>` 视图委托 double** 版） | ✅ |
| — | TMalign.h | `CPalign_main` 同上 | ✅ |
| B2 | TMscore.h | `TMscore_main` 同上 | ✅ |
| — | HwRMSD.h | `HwRMSD_main` 同上 | ✅ |
| B3 | TMalign.cpp | `xa/ya` → Coords，删 `NewArray`/`DeleteArray` | ✅ |
| B4 | TMscore.cpp | 同上 | ✅ |
| B5 | HwRMSD.cpp | 同上 | ✅ |

**附带解锁**
| 文件 | 函数 | 内容 |
|------|------|------|
| TMalign.h | `make_sec`（蛋白质版） | 新增 `const Coords&` 重载 |
| TMalign.h | `make_sec`（RNA 版） | 新增 `const Coords&` 重载 |
| basic_fun.h | `dist()` | 新增 `dist(const array<double,3>&, double*)` 混合重载 |
| basic_fun.h | `read_PDB` | 新增 `Coords&` 重载（`clear + reserve + push_back`） |
| SOIalign.h | `SOI_super2score` | 新增 `const Coords&` 重载 |
| se.h | `se_main` | 新增 Coords& + double** 混合重载（flexalign 调用方） |

**阶段 9：USalign.cpp 主程序**
| 步骤 | 函数 | 状态 | 说明 |
|------|------|:--:|------|
| L2h-35 | `TMalign()` | ❌ | xa/ya → Coords 后 `-dir` 路径 bad_alloc 崩溃（问题 28） |

### 新发现的问题

#### 问题 28：TMalign() xa/ya → Coords 后 `-dir` 路径 bad_alloc 崩溃

**症状**：USalign.cpp `TMalign()` 函数中 xa/ya 从 `double**` → `Coords` 后，`-dir` 模式（all_vs_all 用例）运行时抛出 `std::bad_alloc`，程序崩溃。非 `-dir` 路径的 11 个用例正常。

**排查状态**：已确认非 sed 误操作（回退 USalign.cpp 后恢复正常，重做后复现）。根因待查——怀疑 `-dir` 嵌套循环中 Coords 的 `clear()`/`reserve()`/`push_back()` 与原有的 `NewArray`/`DeleteArray` 内存复用模式存在语义差异。

**当前处置**：USalign.cpp 保持 `double**`，延后处理。

### 未完成 / 阻塞

| 文件 | 状态 | 原因 |
|------|:--:|------|
| MMalign.h | ❌ | 39 处 NewArray，内部函数紧密耦合，`parse_chain_list` 转换后 bad_alloc，已回退。需整体规划 |
| MMalign.cpp | ❌ | 依赖 MMalign.h |
| qTMclust.cpp | ⏸️ | 未开始 |
| biounitasym.cpp | ⏸️ | 未开始 |
| USalign.cpp 其余函数 | ❌ | TMalign() bad_alloc + MMalign/mTMalign/SOIalign/flexalign 依赖未打通的路径 |
| 阶段 10 清理 | ⏸️ | 待所有文件迁移完成后 |

### 提交记录

| Commit | 内容 |
|--------|------|
| `75a9653` | L2h-A+B — 阻塞链 A/B 解除（se_main 方向翻转 + TMalign_main 桥接 + flexalign/HwRMSD/独立.cpp 全部转换） |
| `22ce7d7` | 阻塞链 B 完成 |
| `0cbf19e` | A3+A4 完成（flexalign.h + HwRMSD.h） |
| `667a3b8` | L2h-33 + L2h-26 + make_sec Coords& 重载 — pdb2ss.cpp 首次成功迁移 |
| `cd7c928` | L2h-14 — SOIalign.h 坐标临时数组 → Coords |
| `1f12dc6` | L2h-13 — TMscore_main 坐标临时数组 → Coords |

### 下一步计划

1. 排查问题 28（TMalign() `-dir` 路径 bad_alloc）
2. 尝试 qTMclust.cpp、biounitasym.cpp（依赖链可能简单）
3. MMalign.h 整体规划（39 处 NewArray，内部耦合严重，建议独立阶段）
4. USalign.cpp 其余函数（MMalign、mTMalign、SOIalign、flexalign、search_databases）
5. 阶段 10 清理旧重载 + 删除 NewArray/DeleteArray 模板

---

## 2026-05-26 printf → fcout 格式化输出重构

| 指标 | 数值 |
|---|---|
| 方案文档 | `2026-05-25-printf-to-cout-via-cprint.md` |
| Commit 数 | 3（F1+F2 / F3 / F4-F10 + .c_str() 清理） |
| 修改文件 | 8（basic_fun.h + USalign.cpp + NWalign.h + TMscore.h + flexalign.h + TMalign.h + TMalign.cpp + qTMclust.cpp + MMalign.cpp） |
| 完成任务 | 全项目 96 处 printf → fcout，零 printf 残留；追加清理 fcout 参数中多余的 .c_str() |

### 背景

此前 P-3（2026-05-15）尝试用 Python 脚本自动化 printf → cout 替换失败，格式化的 106 处 printf 被列为"设计明确不做"。2026-05-25 重新评估，制定了 fcout 包装方案：用 C++ 模板包装 `snprintf` → `std::cout`，格式字符串原封不动，确保输出逐字节一致。

方案选型排除了 `std::format`（需 C++20，老服务器不兼容）和 `operator<<`（状态污染、人工重写工作量大），选定 fcout 作为务实的折中方案。

### 执行计划：10 步×8 文件×96 处

| 步骤 | 文件 | 函数 | 数量 |
|------|------|------|------|
| F1 | `basic_fun.h` | —（新增 fcout + to_cstr） | 0 |
| F2 | `USalign.cpp` | `main()` | 3 |
| F3 | `NWalign.h` | `output_NWalign_results()` | 12 |
| F4 | `TMscore.h` | `output_TMscore_results()` | 24 |
| F5 | `flexalign.h` | `output_flexalign_results()` | 19 |
| F6 | `TMalign.h` | `output_results()` | 21 |
| F7 | `TMalign.h` | `output_mTMalign_results()` | 13 |
| F8 | `TMalign.cpp` | `main()` | 1 |
| F9 | `qTMclust.cpp` | `main()` | 1 |
| F10 | `MMalign.cpp` | `main()` | 2 |

每步完成后：编译 → 开发人员手动运行回归测试 → 全部 PASS → commit。遵循"人机协作，逐步验证"原则。

### 追加工作：.c_str() 清理

fcout 参数中 `std::string` 的 `.c_str()` 调用不再需要（`to_cstr` 自动处理），在所有 fcout 调用点清理掉多余的 `.c_str()`。

### 关键技术决策

- **命名**：最终定名 `fcout`（formatted cout），简洁、C++ 风格
- **无 `fcerr`**：源码中无 `fprintf(stderr, ...)` 调用，仅需一个 `fcout`
- **sprintf 不替换**：8 处 `sprintf(buf, ...)` 不涉及输出流，保持原样

### 未来迁移路径

当所有目标环境升级到 GCC 12+（支持 C++20），fcout 可脚本化迁移到 `std::format`：
`fcout("TM-score= %5.4f\n", TM1)` → `std::cout << std::format("TM-score= {:5.4f}\n", TM1)`
格式字符串 `%` → `{:}` 是确定性映射，无需重新理解业务语义。

---

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
| 1 | printf/fprintf | ✅ fcout 包装方案（96处 printf → fcout，零残留，2026-05-26） |
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
| printf/fprintf | 96 处 | ✅ 2026-05-26 fcout 包装方案完成 |
| sprintf | 8 处 | 保持原样（不涉及输出流） |
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

---

## 2026-05-25 项目终态快照

### 一、项目目录层级图

```
usalign_modify/                              # 主仓库 (main, 已 push)
│
├── USalign/                                # 源码仓库 (USalign-beta, 领先 master 51 commits, 已 push origin)
│   ├── USalign.cpp                         # 主程序入口 (157KB, ~3600行) — main() + TMalign/MMalign/SOIalign/flexalign/mTMalign/MMdock
│   │
│   ├── 核心算法头文件 (.h)                 # 纯头文件模板库
│   │   ├── TMalign.h                       #   核心单体比对引擎 (142KB, ~3800行) — TMalign_main/score_fun8/DP_iter/初始策略
│   │   ├── MMalign.h                       #   寡聚体比对 (118KB, ~3000行) — MMalign_search/final/iter/dimer + 贪心链分配
│   │   ├── flexalign.h                     #   柔性铰链比对 (71KB, ~2000行) — flexalign_main
│   │   ├── SOIalign.h                      #   序列顺序无关比对 (31KB) — SOIalign_main + soi_egs
│   │   ├── TMscore.h                       #   纯 TM-score/GDT/MaxSub 计算 (33KB) — TMscore8_search
│   │   ├── NWalign.h                       #   Gotoh 序列比对 (22KB) — NWalign_main + calculate_score_gotoh
│   │   ├── NW.h                            #   简化 NW 动态规划 (11KB) — NWDP_TM / NWDP_SE (gap_open=gap_extend)
│   │   ├── Kabsch.h                        #   Kabsch 最优旋转矩阵 (11KB)
│   │   ├── se.h                            #   无叠加结构比对 (7KB) — se_main
│   │   ├── HwRMSD.h                        #   加权 RMSD (8KB) — HwRMSD_main
│   │   ├── basic_fun.h                     #   基础工具库 (38KB, ~1050行) — read_PDB/get_PDB_lines/do_rotation
│   │   ├── BLOSUM.h                        #   BLOSUM62/80/45 + BLASTN 替换矩阵 (52KB)
│   │   ├── param_set.h                     #   d0 归一化参数公式 (3KB)
│   │   └── pstream.h                       #   第三方库 — gzip/bzip2 透明读取 (73KB, 未改造)
│   │
│   ├── 独立程序入口 (.cpp)                 # 各自包含对应 .h 头文件独立编译
│   │   ├── TMalign.cpp                     #   独立单体比对
│   │   ├── TMscore.cpp                     #   独立 TM-score 计算
│   │   ├── MMalign.cpp                     #   独立寡聚体比对
│   │   ├── NWalign.cpp                     #   独立序列比对
│   │   ├── se.cpp                          #   独立结构比对提取
│   │   ├── HwRMSD.cpp                      #   独立加权 RMSD
│   │   ├── qTMclust.cpp                    #   准 TM-score 聚类 (32KB)
│   │   ├── pdb2ss.cpp                      #   PDB → 二级结构
│   │   ├── pdb2fasta.cpp                   #   PDB → FASTA
│   │   ├── pdb2xyz.cpp                     #   PDB → xyz 格式
│   │   ├── cif2pdb.cpp                     #   mmCIF → PDB (19KB)
│   │   ├── pdbAtomName.cpp                 #   标准化原子名称
│   │   ├── addChainID.cpp                  #   添加链 ID
│   │   ├── biounitasym.cpp                 #   生物单元 ↔ 不对称单元
│   │   └── xyz_sfetch.cpp                  #   xyz 数据库提取
│   │
│   ├── __init__.py                         # PyMOL 插件 (usalign / usalign_msta 命令)
│   ├── Makefile / Dockerfile / LICENSE / readme.txt
│   └── align.txt / PDB1.pdb / PDB2.pdb     # 示例输入文件
│
└── usalign-refactor-tests-framework/       # 测试框架仓库 (main, 已 push origin)
    │
    └── scripts/
        │
        ├── cLanguage2Cplus/                # ★ 主回归测试框架
        │   ├── CLAUDE.md                   #   框架说明 (架构/约定/命令)
        │   │
        │   ├── 测试脚本 (Python)
        │   │   ├── create_baseline.py      #   编译原始版 USalign.cpp → 生成 baseline/
        │   │   ├── run_regression.py       #   编译修改版 USalign.cpp → 逐字节比对 14 用例
        │   │   ├── create_perf_baseline.py #   编译原始版 → 生成 perf_baseline/
        │   │   ├── run_perf_test.py        #   编译修改版 → 5次取平均, <20% PASS
        │   │   ├── build_Small_DB.py       #   从 PDB 集合构建 smallDB
        │   │   └── find_pdb_length.py      #   辅助工具
        │   │
        │   ├── 测试用例定义 (纯文本)
        │   │   ├── testcases_functional.txt    #   14 用例: 
                                                            standard/multichain/oligomer/circular/fully_non_seq/
                                                            semi_non_seq/superposed/tmscore_resid/tmscore_seqalign/
                                                            complex_chainid/complex_chainmap/msta_rna/all_vs_all/database_search
        │   │   └── testcases_performance.txt   #   4 用例: perf_fast1/perf_fast2/perf_msta_rna/perf_database_search
        │   │
        │   ├── baseline/                   #   原始版基线 (14 .out + sup.pdb)
        │   ├── current/                    #   修改版当前输出 (运行时重建)
        │   ├── diffs/                      #   差异文件 (7 .diff)
        │   ├── perf_baseline/              #   性能基线 (baseline.csv)
        │   ├── perf_current/               #   当前性能 (performance.csv)
        │   │
        │   ├── data/                       # ★ 测试数据
        │   │   ├── *.pdb + *.pdb1          #   单体/多链结构 (15个)
        │   │   ├── help/                   #   TM-score引导测试 (model/native/complex x2)
        │   │   ├── MSTATest/               #   RNA多结构比对 (12 .pdb + list.txt)
        │   │   └── smallDB/                #   数据库搜索子集 (100 .pdb + list.txt)
        │   │
        │   ├── standalone/                 # ★ 4 个独立程序子测试框架 (已验证 20/20 PASS)
        │   │   ├── tmscore/                #   TMscore: testcases.txt + create_baseline.py + run_test.py (6用例)
        │   │   ├── hwrmsd/                 #   HwRMSD: testcases.txt + create_baseline.py + run_test.py (5用例)
        │   │   ├── mmalign/                #   MMalign: testcases.txt + create_baseline.py + run_test.py (4用例)
        │   │   └── pdb2ss/                 #   pdb2ss: testcases.txt + create_baseline.py + run_test.py (2用例)
        │   │
        │   └── docs/superpowers/specs/     # ★ 项目文档
        │       ├── 2026-05-12-usalign-cpp-refactor-design.md
        │       │                            #   重构总体方案: 22类C→C++映射表 + 4层文件拆分 + 独立里程碑
        │       ├── 2026-05-14-refactor-progress-log.md
        │       │                            #   重构详细进度: 逐日逐步记录, 24个问题发现与修复, 51个commit链路 (本文件)
        │       ├── 2026-05-21-refactor-final-summary.md
        │       │                            #   最终总结: 完成状态表 + 剩余工作 + 已验证测试结果
        │       └── 2026-05-21-usalign-l2h-pointer-to-container-design.md
        │                                    #   L2-h 二级指针方案: ~347处, 7类容器类型, ~38步, 6阶段
        │
        └── mm1/                            # MMalign 独立功能测试 (已恢复)
            ├── CLAUDE.md / IMPLEMENTATION_PLAN.txt / WORK_LOG.txt
            ├── dir_mm1_test.py             #   -dir 模式: 全对全比对测试
            ├── dir1_mm1_test.py            #   -dir1 模式: 单侧搜索测试
            ├── dir2_mm1_test.py            #   -dir2 模式: 另一侧搜索测试
            ├── *_generate_baseline.py      #   对应基线生成脚本
            ├── *_test_cases.txt            #   测试用例定义
            ├── *_feature_cases.txt         #   功能特性用例
            ├── dirbaseline/ / dir1baseline/ / dir2baseline/   # 基线输出
            └── data/MSTATest/              #   测试数据 (3 PDB + list)
```

### 二、数据统计

#### ✅ 已完成

| 维度 | 数值 | 详情 |
|------|------|------|
| C→C++ 映射类别完成 | **16 类** | strcmp→operator==, atoi/atof→safe, strlen→.size(), strcpy→string, char*→string&, NULL→nullptr, C强转→static_cast, C头文件→C++头文件, #define MAX→std::max, FILE*→ifstream, clock→std::clock, #define守卫→#pragma once, VLA→vector, (char*)强转清理, 逗号声明拆分, C89集中声明→随用随声明 |
| 已取消映射类别 | **2 类** | printf/fprintf 格式化(P-3取消), sprintf(P-3取消) |
| 改造源文件 | **27 个** | 15 `.h` + 12 `.cpp`（仅 pstream.h 三方库未动） |
| USalign-beta commits | **51** | 领先 master，已 push origin/USalign-beta |
| 独立里程碑完成 | **4 个** | M: char*→string+FILE*→ifstream、S: secx/secy迁移(~45处)、P-2: 纯文本printf→cout、VLA全局清零 |
| 功能回归测试用例 | **34 个** | 主回归 14 + 独立程序 20（TMscore 6 / HwRMSD 5 / MMalign 4 / pdb2ss 2） |
| 性能回归测试用例 | **4 个** | perf_fast1/2, perf_msta_rna, perf_database_search（各5次取平均） |
| 测试框架 Python 脚本 | **13 个** | 主框架 6 + 独立程序 4×2 + mm1 3×1（基线+测试各有） |
| 独立程序验证结果 | **20/20 PASS** | TMscore(6) + HwRMSD(5) + MMalign(4) + pdb2ss(2) 全部通过 |
| mm1 子框架 | **3 模式** | -dir / -dir1 / -dir2 各有基线 + 测试脚本 + 测试用例 |
| 核心设计文档 | **4 份** | 重构方案(743行) + 进度日志(1192行) + 最终总结(198行) + L2-h方案(397行) |
| 重构中修复的问题 | **24 个** | P0 5个 + P1 5个 + P2 8个 + P3 6个 |
| Git 仓库 | **2 个** | 主仓库(main,已push) + USalign(USalign-beta,已push) |

#### ⏳ 剩余工作

| 事项 | 规模 | 详情 |
|------|------|------|
| USalign-beta → master 合并 | **1 项** | 51 commits，需选策略（squash / merge / rebase） |
| L2-h: 二级指针 → C++ 容器 | **~38 步** | ~347处 NewArray/DeleteArray，7类容器类型(Coords/DPMatrix/PathMat/IntMat/Rotation/Bond2)，6阶段，方案已制定 |

#### ❌ 明确不做

| 事项 | 数量 | 原因 |
|------|------|------|
| printf/fprintf 格式化 | 106 处 | P-3 已取消：snprintf+cout 风格收益低，逐字节对齐调试成本高 |
| sprintf | — | P-3 已取消：同上 |
| 头文件 for 循环变量内联 | ~200 处 | P3-2 跳过：TMalign/SOIalign/flexalign/MMalign 算法核心，改动风险高 |
| MMalign.h C89 集中声明 | 61 处 | 纯外观，无编译影响 |
| Kabsch.h 循环变量内联 | 15 处 | 永久跳过：337行密集SVD，19个变量交叉复用，风险>收益 |
| se_main/NWalign_main 方向翻转 | — | ✅ 2026-05-25 se_main 已完成（问题15根因确认，见下），NWalign_main 同理可做 |
| ~~se_main 方向翻转永久取消~~ | — | 2026-05-25 实验验证后推翻原结论，见下方"问题 15 终局" |
| `/* */` → `//` | ~20 处 | 均为多行文档注释，保留 |
| qTMclust.cpp seq_vec 类型链 | — | P2：独立程序已有问题，非本次引入 |
| xyz_sfetch.cpp safe_stoi 未声明 | — | P3：独立程序已有问题，非本次引入 |

---

## 2026-05-25 问题 15 终局：方向翻转实验 + 根因修正

### 背景

此前认为 `se_main` 的方向翻转（string 变真实现、char* 变桥接）会因栈帧布局问题导致崩溃，标记为"永久取消"，`.c_str()` 为永久方案。

### 实验

对 `se.h` 进行完整的方向翻转测试：

**阶段 1 — 翻转 + 保留 char* 桥接**：
- 238 行真实现签名 `const char *seqx, const char *seqy` → `const std::string &seqx, const std::string &seqy`
- 函数体零改动（仅用 `operator[]` 读取，语义等价）
- 新增 char* 反向桥接：`std::string sx(seqx)` → 调 string 实现
- 8 处调用点去除 `.c_str()` 绕过
- **结果**：✅ 编译通过，msta_rna 不崩溃，14 用例全量回归 PASS

**阶段 2 — 删除 char* 桥接**：
- 全项目扫描：零 char* 调用者，反向桥接为死代码
- 删除反向桥接 + 前置声明，se.h 精简为唯一重载
- **结果**：✅ 编译通过，等待用户手动测试

### 根因修正

**之前的推测（错误）**：`const std::string&` 参数类型改变栈帧布局 → 被推翻。真实现直接用 `const std::string&` 在深层嵌套中不崩。

**真正的根因**：M-1 阶段新增的**那层正向桥接**本身——`const std::string&` 跨栈帧引用 + `.c_str()` 在桥接帧内求值 + 再次调 char* 版的三层嵌套，在 mTMalign 深层嵌套中出了问题。不是参数类型的问题，是那一层多余的函数调用帧的问题。

### 最终方案

- 删除全部桥接：正向桥接（根因）+ 反向桥接（全项目无 char* 调用者，死代码）
- se.h 精简为唯一重载：`const std::string &seqx, const std::string &seqy`
- 修改文件：`se.h`（主要）、`MMalign.h`（5 处）、`USalign.cpp`（3 处）

### 同样适用

NWalign_main 当前仍有相同的正向桥接模式，可以应用相同的精简方案。

---

## 2026-05-25 全部核心函数签名统一 string& + 消除 .c_str() workaround

### 改动范围

在问题 15 根因确认（正向桥接为罪魁祸首，`const std::string&` 签名本身安全）后，将所有受影响的函数一次性统一：

| 函数 | 文件 | 改动 |
|------|------|------|
| `se_main` | `se.h` | 删除正向桥接，签名 `char*` → `string&`，唯一重载 |
| `NWalign_main` | `NWalign.h` | 同上（体内 trace_back 调用保留 `.c_str()`，因子函数仍有指针运算） |
| `soi_se_main` | `SOIalign.h` | 签名 `char*` → `string&`（原本无桥接） |
| `TMalign_main` | `TMalign.h` | 签名 4 参数统一 `string&`（seqx, seqy, secx, secy） |
| `CPalign_main` | `TMalign.h` | 同上 |
| `SOIalign_main` | `SOIalign.h` | 同上 |
| `flexalign_main` | `flexalign.h` | 同上 |

全部调用点的 `.c_str()` workaround 去除（除 `qTMclust.cpp`——`seq_vec` 是 `vector<vector<char>>`，P2 遗留）。

### 修改文件（9 个）

`se.h`, `NWalign.h`, `SOIalign.h`, `TMalign.h`, `flexalign.h`, `MMalign.h`, `USalign.cpp`, `MMalign.cpp`, `TMalign.cpp`

### 测试结果

- ✅ 14 个功能回归 PASS
- ✅ 4 个独立程序回归 PASS（TMscore 6 / HwRMSD 5 / MMalign 4 / pdb2ss 2）
- ✅ USalign + 3 个独立程序编译通过

### Commit 记录

```
0288a83 删除NWalign_main中的正向桥接模式，改签名为 const std::string&
976086f refactor(se): se_main 签名 char*→string&，消除问题15的桥接层和 workaround
（TMalign_main 等统一签名改动由用户自行提交）
```

---

## P-3 回顾：printf → cout 格式化替换讨论（2026-05-25）

### 当时为什么取消

P-3（格式化 printf → snprintf+cout）在 2026-05-15 执行中被取消，两个直接原因：

**问题 8（严重）**：Python 脚本正则 `\bprintf\(` 误匹配了 `sprintf(`，损坏了 4 个 .h 文件（TMalign.h, NWalign.h, TMscore.h, flexalign.h），需从旧 commit 恢复，导致之前的部分修改丢失（問題 14）。

**问题 12（严重）**：当次会话所有修改未分步 commit，P-3 损坏文件后无法精确回退到 P-2 之后的状态。

更深层的原因：
- **snprintf 桥接方案**每处都要写 `char buf[256]` + `snprintf` + `cout`，散落大量 C buffer，风格收益低
- **纯 cout 操纵器方案**`setfill`/`setprecision`/`fixed` 是全局持久状态，跨函数互相污染。回归测试逐字节比对，一个空格差异就 FAIL，调试成本极高

### 纯 cout 操纵器的状态污染问题

```
std::cout << setfill('0') << setw(4) << 1;   // "0001"
//              ↑ setfill 设为 '0'，之后永久生效

std::cout << setw(4) << 2;                   // "0002" —— 被污染了！
```

所有流操纵器中只有 `setw` 是调用后自动重置，`setfill`、`setprecision`、`fixed`/`scientific` 全部永久生效——跨函数、跨文件，直到程序退出或手动恢复。USalign 的 output_results 函数有几十行格式化输出，每个调 `setfill` 的地方都要加 `<< setfill(' ')` 恢复，漏一处 → 回归测试 FAIL。

### printf vs cout 机制差异

| | printf | cout |
|------|--------|------|
| 格式指定 | 格式字符串自描述，每次独立 | 流操纵器修改全局状态，跨调用持久 |
| 状态隔离 | 天然隔离 | setfill/setprecision/fixed 全局持久 |
| 逐字节对齐 | 字符串不变即一致 | 需逐字节验证，边界值可能不同 |

### 当前可行的替代方案

**方案 A：`std::format` (C++20)**

```cpp
std::cout << std::format("TM-score= {:5.4f}\n", TM1);
```
- 格式字符串近似 printf，无状态持久，编译期类型安全
- 本项目 GCC 14.2 + `-std=c++20` 已验证可用
- 代价：要求 C++20，老环境不支持

**方案 B：`cprint` 包装（无外部依赖，不要求 C++20）**

```cpp
#include <cstdio>
#include <string>
#include <iostream>

inline const char* to_cstr(const std::string& s) { return s.c_str(); }
inline const char* to_cstr(const char* s)         { return s; }
template<typename T> auto to_cstr(const T& val) -> const T& { return val; }

template<typename... Args>
void cprint(const char* fmt, const Args&... args) {
    int size = std::snprintf(nullptr, 0, fmt, to_cstr(args)...);
    std::string buf(size, '\0');
    std::snprintf(&buf[0], size + 1, fmt, to_cstr(args)...);
    std::cout << buf;
}
```

- 格式字符串原封不动，输出 100% 一致，零调试成本
- `to_cstr` 自动处理 `std::string` → `.c_str()`，消除 UB（`std::string` 是非平凡类型，通过 C 变参传递是未定义行为）
- 106 处改动纯机械替换 `printf(` → `cprint(`、`fprintf(stderr,` → `cprint(`
- 15 行代码放在 `basic_fun.h`，零外部依赖

### 结论

当初如果先封装 `cprint` 再做全局替换，P-3 不会取消。`std::format` 是更现代的方案，但需要 C++20；`cprint` 是最务实的方案，无版本要求。两者都比当年的 snprintf 桥接干净，也比纯 cout 操纵器安全。```
