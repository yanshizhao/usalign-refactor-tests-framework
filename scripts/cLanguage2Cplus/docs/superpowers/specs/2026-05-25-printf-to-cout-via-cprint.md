# printf → cout 格式化重构：fcout 包装方案

**日期**: 2026-05-25
**状态**: 方案已制定，待启动
**涉及文件**: 8 个源码文件，~96 处 printf

---

## 一、背景

P-3（2026-05-15）尝试用 Python 脚本自动化 printf → cout 替换，因正则误匹配损坏文件、snprintf 桥接风格收益低、cout 操纵器状态污染等问题被取消。纯文本 printf→cout（P-2）已保留。

本次重新启动，方案选型上考虑了三种路径：

| 方案 | C++ 风格 | 类型安全 | 老服务器兼容 | 替换难度 | 结论 |
|------|----------|----------|-------------|---------|------|
| **std::format**（C++20） | 严格 | 是 | 否（老 GCC 不支持） | 中 | ❌ 兼容性风险 |
| **operator<<** | 严格 | 是 | 是 | 高（每处人工重写） | ❌ 工作量大、状态污染 |
| **fcout**（snprintf 包装） | 折中 | 部分 | 是 | 低（机械替换） | ✅ 选定 |

最终选定 **fcout 包装方案**——用 C++ 模板包装 printf 格式字符串，通过 `snprintf` → `std::cout` 输出，保持格式字符串原封不动，最大化降低回归风险。

---

## 二、fcout 详细实现

### 2.1 核心代码

放置在 `basic_fun.h` 中，全项目通过 include 链自动可见：

```cpp
// ============================================================
// fcout — C++ wrapper around printf for std::cout output
// Replaces: printf("format", ...) → fcout("format", ...)
// The format string is passed through snprintf unchanged,
// guaranteeing byte-identical output with the original printf.
// ============================================================

// ---- argument conversion helpers ----

// std::string → const char*
inline const char* to_cstr(const std::string& s) { return s.c_str(); }

// const char* — identity pass-through
inline const char* to_cstr(const char* s)         { return s; }

// char — identity pass-through (%c)
inline char to_cstr(char c)                      { return c; }

// All other types (int, double, etc.) — identity pass-through
template<typename T>
inline T to_cstr(const T& val) { return val; }

// ---- fcout ----

// Primary template: snprintf → std::cout
template<typename... Args>
void fcout(const char* fmt, const Args&... args) {
    int size = std::snprintf(nullptr, 0, fmt, to_cstr(args)...);
    if (size <= 0) return;
    std::string buf(size, '\0');
    std::snprintf(&buf[0], size + 1, fmt, to_cstr(args)...);
    std::cout << buf;
}

// No-argument overload (const char* → direct cout, no snprintf overhead)
inline void fcout(const char* fmt) {
    std::cout << fmt;
}
```

### 2.2 to_cstr 的必要性

`std::string` 是非平凡类型（non-trivially-copyable），通过 C 变参 `...` 传给 `snprintf` 是**未定义行为**（C++ 标准 [expr.call]/7）。`to_cstr` 在参数进入变参之前，把 `std::string` 显式转为 `const char*`，消除 UB。

在 GCC/MinGW 14.2 上，`std::string` 对象前 8 字节恰好是 `_M_p`（内部数据指针），`snprintf` 读这 8 字节当 `const char*` 也许"恰好正常工作"。但这是未定义行为，不能依赖。

### 2.3 为什么格式字符串可以原封不动

`snprintf` 的格式字符串语法与 `printf` 完全相同：

```
printf: printf("TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);
fcout:  fcout("TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);
```

格式字符串一个字不改。`snprintf` 先写入 `std::string buf`，再 `std::cout << buf`。输出逐字节完全一致。

---

## 三、执行计划

### 设计原则

- **每步一文件一函数**：一步只改一个文件的**一个输出函数**，改动量控制在 ~20 处以内
- **每步独立可验证**：改完立即编译，编译通过后由开发人员手动运行回归测试，输出必须与 master 基线逐字节一致
- **每步独立可提交**：回归通过后单独 commit 并 push 到 GitHub 远程仓库，再继续下一步；失败时只需 `git checkout` 一个文件即可回退
- **禁止跨文件一步**：绝不把多个文件的 printf 合并到一步
- **人机协作流程**：每步的流程为：修改代码 → 编译通过 → 提示开发人员手动执行测试 → 开发人员确认测试 PASS → commit & push → 继续下一步

### printf 分布总览

| 文件 | 函数 | printf 数 |
|------|------|----------|
| `TMalign.cpp` | `main()` CPU time | 1 |
| `qTMclust.cpp` | `main()` CPU time | 1 |
| `MMalign.cpp` | `main()` CPU time | 2 |
| `USalign.cpp` | `main()` help + CPU time | 3 |
| `NWalign.h` | `output_NWalign_results()` | 12 |
| `TMscore.h` | `output_TMscore_results()` | 24 |
| `flexalign.h` | `output_flexalign_results()` | 19 |
| `TMalign.h` | `output_results()` | ~21 |
| `TMalign.h` | `output_mTMalign_results()` | ~13 |

---

### 阶段 1：基础设施 — 添加 fcout，不改任何 printf

| 步骤 | 文件 | 内容 | printf 改动 |
|------|------|------|------------|
| **F1** | `basic_fun.h` | 在文件末尾添加 `fcout` + `to_cstr` 定义 | 0（仅新增代码） |

**验证**：`g++ -O3 -ffast-math -lm -o USalign.exe USalign.cpp` 编译通过即可，不跑回归（无改动，输出必然一致）。

**Commit**: `add fcout wrapper to basic_fun.h`

---

### 阶段 2：主入口 — USalign.cpp

| 步骤 | 文件 | 位置 | 内容 |
|------|------|------|------|
| **F2** | `USalign.cpp` | lines 1314,1647,3661 | 3 处 `printf(...)` → `fcout(...)` |

**验证**：编译 USalign.cpp → `run_regression.py`（14 用例全部 PASS）

**Commit**: `printf → fcout in USalign.cpp`

---

### 阶段 3：中型输出函数 — 按函数拆分

| 步骤 | 文件 | 函数 | printf 数 |
|------|------|------|----------|
| **F3** | `NWalign.h` | `output_NWalign_results()` | 12 |

**验证**：编译 USalign.cpp → `run_regression.py`

> `output_NWalign_results()` 不被 USalign 的代码路径调用，但编译验证无语法错误。该函数由独立 `NWalign.cpp` 使用，当前无独立 NWalign 回归测试，以编译通过为准。

**Commit**: `printf → fcout in output_NWalign_results()`

---

### 阶段 4：大型输出函数 — 每步一个函数

| 步骤 | 文件 | 函数 | printf 数 |
|------|------|------|----------|
| **F4** | `TMscore.h` | `output_TMscore_results()` | 24 |
| **F5** | `flexalign.h` | `output_flexalign_results()` | 19 |
| **F6** | `TMalign.h` | `output_results()` | ~21 |
| **F7** | `TMalign.h` | `output_mTMalign_results()` | ~13 |

**每步验证**：编译 USalign.cpp → `run_regression.py`（14 用例全部 PASS）

**F4 额外验证**：`cd standalone/tmscore && python run_test.py`

**Commit**: `printf → fcout in <function_name>()`

---

### 阶段 5：独立程序 — 单文件、单 printf 调用

最后处理独立 `.cpp` 可执行文件，每步改一个 `main()` 函数。

| 步骤 | 文件 | 位置 | 内容 |
|------|------|------|------|
| **F8** | `TMalign.cpp` | line 668 | `printf("#Total CPU time...")` → `fcout(...)` |
| **F9** | `qTMclust.cpp` | line 809 | `printf("#Total CPU time...")` → `fcout(...)` |
| **F10** | `MMalign.cpp` | lines 482,846 | 2 处 `printf("#Total CPU time...")` → `fcout(...)` |

**每步验证**：编译 USalign.cpp → `run_regression.py`（14 用例全部 PASS）

**F10 额外验证**：`cd standalone/mmalign && python run_test.py`

**Commit**: `printf → fcout in TMalign.cpp` / `qTMclust.cpp` / `MMalign.cpp`

---

### 汇总：10 步×8 文件×~96 处

| 步骤 | 文件 | 函数 | 数量 |
|------|------|------|------|
| F1 | `basic_fun.h` | —（新增代码） | 0 |
| F2 | `USalign.cpp` | `main()` | 3 |
| F3 | `NWalign.h` | `output_NWalign_results()` | 12 |
| F4 | `TMscore.h` | `output_TMscore_results()` | 24 |
| F5 | `flexalign.h` | `output_flexalign_results()` | 19 |
| F6 | `TMalign.h` | `output_results()` | ~21 |
| F7 | `TMalign.h` | `output_mTMalign_results()` | ~13 |
| F8 | `TMalign.cpp` | `main()` | 1 |
| F9 | `qTMclust.cpp` | `main()` | 1 |
| F10 | `MMalign.cpp` | `main()` | 2 |

---

## 四、风险与应对

### 4.1 替换遗漏

**风险**：部分 printf 格式较复杂（跨行、宏内部、条件编译），机械替换可能遗漏。

**应对**：替换前 `grep -n 'printf\b' *.cpp *.h | grep -v pstream.h` 建立完整清单，替换后再扫一遍确认清零。

### 4.2 `std::string` 参数漏加 `.c_str()`

**风险**：有 `to_cstr` 自动处理，理论上不需要手动 `.c_str()`。但 `to_cstr` 的重载决议在某些边界情况可能选错（如 `const char* const&`）。

**应对**：GCC 带参数 `-Wall -Wextra` 不会对此产生警告，但仍需每个步骤后运行全量回归测试验证输出一致性。

### 4.3 `snprintf(nullptr, 0, ...)` 的可移植性

**风险**：`snprintf(nullptr, 0, ...)` 在 C99 中为合法行为，GCC/MinGW 正常。但少数嵌入式平台或 MSVC 旧版可能不支持。

**应对**：本项目仅在 GCC/MinGW 14.2 + Windows 下编译，不受影响。

### 4.4 性能

**风险**：每次 fcout 调用触发一次 `snprintf` 计算大小 + 一次 `std::string` 堆分配 + 一次 `snprintf` 格式化 + `cout <<`。

**应对**：输出函数不在热路径（非 Kabsch/score_fun8/NWDP_TM），影响可忽略。如需验证，阶段 2 完成后运行性能回归测试。

---

## 五、替换规则速查表

| 原始代码 | 替换为 |
|---------|--------|
| `printf("...", a, b, c)` | `fcout("...", a, b, c)` |
| `printf("usage...\n")`（纯文本，无参数） | `fcout("usage...\n")`（走无参重载） |
| `printf("...%s...", yname.c_str(), ...)` | `fcout("...%s...", yname, ...)`（去掉 `.c_str()`，由 `to_cstr` 自动处理） |

**不替换**：
- `sprintf(buf, ...)` — 不涉及输出流，保持原样
- `pstream.h` — 第三方库
- 已用 `std::cout <<` 的地方 — 已经替换过，不再碰

---

## 六、验证策略

### 每步必做（F2 到 F10）

```bash
cd scripts/cLanguage2Cplus
python run_regression.py    # 14 个功能用例，必须全部 PASS
```

输出必须与 master 基线**逐字节完全一致**。有 diff 立即排查该步骤的修改，不得带着 FAIL 进入下一步。

### 性能验证（全部步骤完成后）

```bash
python run_perf_test.py     # 4 个性能用例，<20% 变化
```

### 特定步骤额外验证

| 步骤 | 额外测试 | 原因 |
|------|---------|------|
| F4 | `cd standalone/tmscore && python run_test.py` | TMscore.h 被独立 TMscore 使用 |
| F10 | `cd standalone/mmalign && python run_test.py` | MMalign.cpp 独立可执行文件 |

---

## 七、与 cout 操纵器方案的对比

| 维度 | fcout 包装 | cout 操纵器 |
|------|-----------|------------|
| 格式字符串 | 原封不动 | 逐个拆解为 `<< setw << setprecision` |
| 输出一致性 | 100% 逐字节一致 | 需逐字节调试对齐 |
| 状态污染 | 无（每次独立调 snprintf） | setfill/setprecision 全局持久 |
| 替换方式 | 机械文本替换 | 每个 printf 需人工重写 |
| 可读性 | 格式字符串保持紧凑 | 冗长的流操纵器链 |
| 外部依赖 | 无 | 无 |
| C++ 版本 | C++14+ | C++11+ |
| 性能 | snprintf × 2 + string 构造 | 直接写入流 |

---

## 八、未来迁移：fcout → std::format

当所有目标编译环境升级到 GCC 12+ / Clang 14+（支持 C++20 `std::format`），可将 fcout 进一步替换为真正的 C++ 惯用方案。此时迁移成本很低——本质仍是机械替换。

### 8.1 触发条件

- 所有生产服务器 GCC ≥ 12（或 Clang ≥ 14）
- 编译选项已启用 `-std=c++20`

### 8.2 迁移步骤

1. **格式字符串批量转换**

   printf 格式与 `std::format` 格式对照：

   | printf | std::format | 说明 |
   |--------|-------------|------|
   | `%d` | `{}` | 整数 |
   | `%s` | `{}` | 字符串 |
   | `%f` | `{}` | 浮点 |
   | `%5.4f` | `{:5.4f}` | 指定宽度和精度 |
   | `%.3f` | `{:.3f}` | 仅指定精度 |
   | `%4d` | `{:4d}` | 指定宽度 |
   | `%02d` | `{:02d}` | 零填充 |
   | `%%` | `{` → 字面花括号 `{{` / `}}` | 需特殊处理 |
   | `\n` | `\n` | 不变 |

   转换脚本可以一键完成——`%` 到 `{:}` 的规则是确定性的。

2. **fcout → std::cout + std::format 替换**

   ```cpp
   // 当前
   fcout("TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);

   // 迁移后
   std::cout << std::format("TM-score= {:5.4f}  (d0= {:.3f})\n", TM1, d0);
   ```

3. **删除旧代码**

   从 `basic_fun.h` 中移除 `fcout`、`to_cstr` 的定义。

4. **回归验证**

   ```bash
   python run_regression.py   # 全部 PASS 后才能确认迁移成功
   ```

### 8.3 为什么迁移成本低

fcout 的格式字符串是**纯 printf 语法**，与 `std::format` 的 `{...}` 语法之间是**确定性映射**——大部分 `%` 就是 `{}`，带宽度精度的 `%5.4f` 就是 `{:5.4f}`。不存在语义歧义，可以完全脚本化转换。

这是当时选择 fcout 而非 operator<< 的一个重要原因：fcout 保留了格式化语义的原子性，不会被拆散成碎片，所以再向 std::format 迁移时不需要重新理解每处输出的业务含义。
