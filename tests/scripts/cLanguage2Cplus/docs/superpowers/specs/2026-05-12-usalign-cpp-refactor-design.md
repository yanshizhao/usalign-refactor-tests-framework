# USalign C 风格 → C++ 风格重构设计

## 目标

将 USalign 项目中所有 C 语言**编码风格**（库函数调用方式）和 **C 语言语法风格**（变量声明、注释、数组、强转等语言层面的写法）全部替换为 C++ 风格，统一整个项目的编码和语法风格为 C++。**仅做风格重构，不改变任何功能行为。**

## 核心策略

> **绝对铁律：底层函数签名变更必须隔离。** `basic_fun.h` 等被全项目 include 的头文件，其函数签名变更（如 `char*` → `string`、`FILE*` → `ifstream`、`atoi` → `safe_stoi`）会瞬间导致所有调用点编译失败。此类变更**绝不能在常规层级步骤中直接修改底层签名**，必须通过以下两种方式之一隔离：
> 1. **重载过渡**：新增 C++ 风格重载（内部为真正实现），原 C 风格签名保留为薄包装器。迁移调用点后，最后一步删除包装器。
> 2. **延后到独立里程碑**：将签名变更集中到独立的里程碑阶段，在所有常规层级改造完成且基线稳定后执行。
>
> 违反此铁律的典型后果：某层级步骤修改了底层签名 → 编译瞬间爆炸 → 几十个文件的编译错误混杂在一起 → 无法定位是签名变更还是当前步骤其他修改导致 → 被迫 `git reset --hard`。

- **方案**：逐文件全量重构，自底向上推进
- **分支**：在 `USalign/` 仓库中创建本地分支 `USalign-beta`，所有改动提交到此分支，**不 push**
- **粒度**：每层按 C 风格类别拆分为小步骤，每个步骤只改一种 C 模式、涉及 1-2 个文件
- **验证**：每步完成后运行回归测试（14 个功能用例 + 4 个性能用例），全部 PASS 后输出本次修改摘要
- **签署**：提示开发人员进行手动测试，开发人员确认通过后，才进入下一步重构
- **记录**：每个步骤一个 Git commit，commit message 描述改了什么、为什么改
- **回退**：出问题时 `git reset --hard HEAD~1` 秒级回退到上一步

## C 风格 → C++ 风格映射表

### 一、编码风格（库函数 / API 层面）

| # | C 风格 | → | C++ 替代 |
|---|---|---|---|
| 1 | `printf(...)` / `fprintf(...)` | → | **延后到最后独立处理**（与 `output_results` 等核心输出函数一起，构成独立里程碑） |
| 2 | `sprintf(buf, ...)` | → | **延后到最后独立处理**（与上一条一起） |
| 3 | `strcmp(a, b)` | → | `a == b`（string 直接比较） |
| 4 | `atoi(s)` / `atof(s)` | → | `safe_stoi(s)` / `safe_stod(s)`（安全包装函数，**必须提供 `const char*` 和 `const std::string&` 双重重载**以避免隐式 string 构造开销，见风险控制） |
| 5 | `strlen(s)` | → | `s.size()` / `s.length()` |
| 6 | `strcpy(dst, src)` | → | `dst = src`（string 赋值） |
| 7 | `char*` 序列/字符串参数 | → | `const std::string&` 或 `std::string_view`（独立里程碑，见下文） |
| 8 | `NULL` | → | `nullptr`（**仅限指针上下文**；整型上下文中的 `NULL` 改为 `0`，见风险控制） |
| 9 | `(type)expr` C 风格强转 | → | `static_cast<type>(expr)` |
| 10 | `<stdio.h>` `<stdlib.h>` `<math.h>` `<string.h>` `<time.h>` | → | `<cstdio>` `<cstdlib>` `<cmath>` `<cstring>` `<ctime>` |
| 11 | `#define MAX(A,B)` | → | `std::max<>()` |
| 12 | `char msg[N]` | → | `std::string` / `std::ostringstream` |
| 13 | `FILE*` / `fopen` / `fclose` | → | **延后到 char* → string 独立里程碑**（与 `read_PDB`、`get_PDB_lines` 等函数签名改造同步进行，采用相同的反向桥接策略） |
| 14 | `clock()` | → | `std::clock()`（`<ctime>` 中即为 C++ 标准库；`std::chrono::steady_clock` 测量墙上时间，与 CPU 时间语义不同，**不可替换**，否则破坏性能测试框架） |
| 15 | `#define` 头文件保护 | → | `#pragma once` |                                                                                                                     |                                                                                                                                 |  |

### 二、语法风格（语言结构层面）
| # | C 语法 | → | C++ 替代 |
|---|---|---|---|
| 16 | `int arr[n]`（n 非编译期常量，VLA） | → | 先做**热点分析**：非热点 → `std::vector<int> arr(n)`；热点 → 保留 VLA 或 `thread_local static std::vector` + `resize()` 复用（详见下文"VLA 热点分析策略"） |
| 17 | `/* ... */` C 风格块注释 | → | `//` 行注释 |
| 18 | `int i; for(i=0;...)` 循环外声明 | → | `for(int i=0; ...)` 循环内声明 |
| 19 | `(char *)"-"` 不必要的强转 | → | 直接用 `std::string`，无需强转 |
| 20 | `int a, b;` 逗号合并声明 | → | `int a;` 换行 `int b;` 每行独立 |
| 21 | 函数入口集中声明所有变量（C89） | → | 变量随用随声明，靠近首次使用处 |
| 22 | `double **xa` / `int **S` 裸二级指针（二维数组） | → | `std::vector<std::vector<T>>` 或 `std::vector<T*>`（~347 处，21 个文件）**【本次不做，延后到性能优化阶段】** |
## 不修改的文件

- `pstream.h` — 第三方库，保持原样
- `USalign.exe` — 预编译二进制，不属于源码

## 文件层级与步骤拆分

### 第 0 层：工具/常量头文件（~10 步）

| 步骤 | 文件          | 改动内容                                                                    |
| ---- | ------------- | --------------------------------------------------------------------------- |
| L0-1 | `BLOSUM.h`    | C 头文件 → C++ 头文件（`<stdio.h>`→`<cstdio>` 等）                          |
| L0-2 | `BLOSUM.h`    | `NULL` → `nullptr`（先确认均为指针上下文，无整型 `NULL`）                    |
| L0-3 | `BLOSUM.h`    | `#define` 头文件保护 → `#pragma once`；`#define` 字母表常量 → `constexpr`（需确认宏未被 `#ifdef` 等预处理条件引用后再替换）   |
| L0-4 | `BLOSUM.h`    | C 块注释 `/* */` → `//`                                                     |
| L0-5 | `param_set.h` | C 头文件 `<math.h>` → `<cmath>`                                             |
| L0-6 | `param_set.h` | `NULL` → `nullptr`（先确认均为指针上下文）；C 风格转换 → `static_cast`；逗号声明拆分 |
| L0-7 | `Kabsch.h`    | C 头文件 → C++ 头文件；`NULL` → `nullptr`（先确认均为指针上下文）            |
| L0-8 | `Kabsch.h`    | C 风格转换 `(double)x` `(int)x` → `static_cast`；`#define` → `#pragma once` |
| L0-9 | `Kabsch.h`    | C 块注释 `/* */` → `//`；循环外声明 → 循环内声明                            |
| L0-R | 全部          | 回归测试验证，确认第 0 层无功能回归                                         |

### 第 1 层：基础函数库 `basic_fun.h`（~13 步）

> **注意**：`char*` 序列/字符串参数 → `const std::string&` 的改造不在本层执行。由于 `basic_fun.h` 被全项目所有文件 include，函数签名变更会导致所有调用点级联修改，因此作为**独立里程碑**单独处理（见下文）。

| 步骤  | 改动类别   | 具体改动内容                                           |
| ----- | ---------- | ------------------------------------------------------ |
| L1-1  | 头文件     | C 头文件 → C++ 头文件                                  |
| L1-2  | 空指针     | `NULL` → `nullptr`（约 55 处，**分两阶段**：(1) 先用 `grep` 列出所有 `NULL`，逐处判定是指针上下文还是整型上下文；(2) 指针上下文改为 `nullptr`，整型上下文改为 `0`。判定规则见风险控制） |
| L1-3  | 字符串转换 | `atoi()` → `safe_stoi()`：在 `basic_fun.h` 中新增，**同时提供 `const char*` 和 `const std::string&` 两个重载**。`const char*` 重载内部用 `strtol` 避免隐式 `std::string` 构造开销；`const std::string&` 重载用 `std::stoi` + try-catch。默认值行为与 `atoi` 一致（解析失败返回 0） |
| L1-4  | 字符串转换 | `atof()` → `safe_stod()`：同上双重重载。`const char*` 重载用 `strtod`，`const std::string&` 重载用 `std::stod` + try-catch。默认值 0.0 |
| L1-5  | 错误缓冲   | `char message[N]` → `std::string`                      |
| L1-6  | 文件操作   | **跳过**，`FILE*` / `fopen` / `fclose` → `std::ifstream` 延后到 char* → string 独立里程碑（与函数签名改造同步） |
| L1-7  | 类型强转   | C 风格强转 `(type)x` → `static_cast<type>(x)`          |
| L1-8  | 头文件保护 | `#define` 头文件保护 → `#pragma once`                  |
| L1-9  | 注释       | C 块注释 `/* */` → `//`                                |
| L1-10 | 变量声明   | `int i; for(i=0;...)` → `for(int i=0; ...)` 循环内声明 |
| L1-11 | 变量声明   | 逗号合并声明 `int a, b;` → 每行独立                    |
| L1-12 | 变量声明   | C89 集中声明 → 随用随声明                              |
| L1-13 | 命名空间   | **从所有头文件中移除 `using namespace std;`**（C++ 反模式：头文件中的 using-directive 会污染所有 include 方的全局命名空间，未来引入与 `std` 同名的自定义符号时导致诡异的编译冲突）。移除后在头文件中对 `cout`/`cerr`/`endl`/`string`/`vector`/`map`/`ifstream`/`max`/`min`/`swap` 等所有 std 标识符添加 `std::` 前缀。`.cpp` 文件中的 `using namespace std;` 保留（作用域局域化，影响可控）。详见风险控制 |
| L1-R  | 回归验证   | 运行全部功能测试 + 性能测试，确认第 1 层无回归         |

### 第 2 层：算法核心头文件（~40 步）

涉及文件：`NWalign.h`、`se.h`、`TMalign.h`、`TMscore.h`、`flexalign.h`、`SOIalign.h`、`MMalign.h`、`HwRMSD.h`

每个文件约 4-6 步，按以下类别依次处理：

| 步骤与类别             | 具体改动内容                                                                                                      |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **a** — 头文件与空指针 | C 头文件 → C++ 头文件；`NULL` → `nullptr`（先确认指针上下文）；若该头文件有独立的 `using namespace std;` → 移除，并对本文件内所有 std 标识符添加 `std::` 前缀（`basic_fun.h` 的 using-directive 在 L1-13 移除后，L2 头文件中若有独立的 using-directive 会成为新的污染源） |
| **b** — 输出方式       | **跳过**，`printf` / `sprintf` → `std::cout` / `std::ostringstream` 延后到最后独立里程碑处理 |
| **c** — 字符串参数类型 | `char*` 序列参数 → `const std::string&` / `std::string_view`**【延后至独立里程碑，不在本层执行】** |
| **d** — C 字符串函数   | `strlen` / `strcmp` / `strcpy` → string 方法；去除 `(char*)` 强转；`atoi/atof` → `safe_stoi`/`safe_stod`（调用双重重载，编译器自动选择最优版本） |
| **e** — 类型转换与计时 | C 风格强转 → `static_cast`；`clock()` → `std::clock()`（仅加 `std::` 前缀，不改计时方式）                         |
| **f** — 可变长数组     | 先做热点分析：非热点 → `std::vector`；热点 → 保留 VLA 或 `thread_local static vector`+`resize()`复用（详见"VLA 热点分析策略"） |
| **g** — 注释与变量声明 | 块注释 `/* */` → `//`；循环外声明 → 循环内声明；逗号声明拆分                                                      |
| **h** — 二级指针       | `double **` / `int **` / `bool **` → `std::vector<std::vector<T>>`（~347 处）**【本次不做，延后到性能优化阶段】** |

### 第 3 层：算法入口 cpp 文件（~20 步）

涉及文件：`TMalign.cpp`、`MMalign.cpp`、`TMscore.cpp`、`NWalign.cpp`、`HwRMSD.cpp`、`se.cpp`、`qTMclust.cpp`

| 步骤与类别             | 具体改动内容                                                 |
| ---------------------- | ------------------------------------------------------------ |
| **a** — 头文件与空指针 | C 头文件 → C++ 头文件；`NULL` → `nullptr`（先确认指针上下文） |
| **b** — 命令行参数解析 | `strcmp()` → `std::string::operator==`                       |
| **c** — 字符串转数值   | `atoi()` / `atof()` → `safe_stoi()` / `safe_stod()`（调用 L1-3/L1-4 中定义的双重重载） |
| **d** — 输出与错误缓冲 | `char message[N]` → `std::string`；`printf` → `std::cout` **延后到最后独立里程碑** |
| **e** — 注释与变量声明 | 块注释 `/* */` → `//`；循环外声明 → 循环内声明；逗号声明拆分 |

### 第 4 层：主程序 + 工具 cpp 文件（~20 步）

涉及文件：`USalign.cpp`、`cif2pdb.cpp`、`biounitasym.cpp`、`pdb2fasta.cpp`、`pdb2ss.cpp`、`pdb2xyz.cpp`、`pdbAtomName.cpp`、`addChainID.cpp`、`xyz_sfetch.cpp`

每个文件按以下类别依次处理：

| 步骤与类别             | 具体改动内容                                                                              |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| **a** — 头文件与空指针 | C 头文件 → C++ 头文件；`NULL` → `nullptr`（先确认指针上下文） |
| **b** — 命令行参数解析 | `strcmp()` → `std::string::operator==`                                                    |
| **c** — 字符串转数值   | `atoi()` / `atof()` → `safe_stoi()` / `safe_stod()`（调用双重重载） |
| **d** — 输出与错误缓冲 | `char message[N]` → `std::string`；`printf` → `std::cout` 和 `sprintf` → `std::ostringstream` **延后到最后独立里程碑** |
| **e** — 类型转换与计时 | C 风格强转 → `static_cast`；`clock()` → `std::clock()`（仅加 `std::` 前缀，不改计时方式） |
| **f** — 注释与变量声明 | 块注释 `/* */` → `//`；循环外声明 → 循环内声明；逗号声明拆分                              |

### 独立里程碑：`char*` → `std::string` + `FILE*` → `std::ifstream`

> **前置条件**：第 0-4 层全部完成并通过回归测试后，再启动此里程碑。

**背景**：`basic_fun.h` 被全项目所有文件 include。两类 C 风格签名——`char*` 参数和 `FILE*` 文件句柄——集中出现在 `read_PDB`、`get_PDB_lines` 等核心函数中。任一签名变更都会导致所有调用点（跨越 4 层、~20 个文件）级联修改。若在 L1 层早期进行，一旦出问题难以定位是底层签名变更还是上层适配错误。

**为什么 FILE* → ifstream 不能留在 L1-6 单独做？** 原因与 char* 完全相同：`basic_fun.h` 中的函数签名如果包含 `FILE*` 参数，改为 `std::ifstream&` 后所有调用点同步编译失败。即使 FILE* 仅作为函数内部局部变量（不暴露在签名中），也不应在 L1 层做——因为 M-1 重写实现时顺手替换为 ifstream 效率更高，避免同一段代码被改两次。因此 FILE* → ifstream 与 char* → string **合并到同一里程碑**。

**策略**：采用**重载过渡 + 反向桥接**方式。核心原则：**真正的实现在 `std::string` + `std::ifstream` 版本中**，`char*` + `FILE*` 版本退化为薄包装器。

**为什么不用 c_str() 正向桥接？** 如果 `char*` 版本内部有指针运算（如 `while(*p == ' ') p++;`），新 string 重载通过 `c_str()` 调用它只是把问题藏起来——M-3 删除 `char*` 版本时仍需面对所有指针运算的重写工作。反向桥接将指针运算和 FILE* 的改造集中到 M-1 一步，M-2 纯机械迁移，M-3 纯删除。

| 步骤 | 改动内容 |
| --- | --- |
| M-1 | 在 `basic_fun.h` 中为每个受影响的函数新增 `const std::string&` 重载，**内部使用 string 方法 + ifstream 完整重写**（`operator[]`、迭代器、`find`、`substr` 替代指针运算；`std::getline` 替代 `fgets`；`>>` 替代 `fscanf`）。然后将原 `char*` 版本改为**薄包装器**：转换为 `std::string` 后调用新重载。例如：`int read_PDB(char* lines, ...) { return read_PDB(std::string(lines), ...); }`。此步零调用点修改，零风险 |
| M-2 | 逐文件将调用点中的 `char*` 实参升级为 `std::string`（调用方可能已有 string 变量，或需要从 `char*` 转为 string）。每迁移 1-2 个文件后运行回归测试 |
| M-3 | 确认所有调用点迁移完成后，删除所有 `char*` 薄包装器。此时 FILE* 相关的旧代码也随薄包装器一并清除。全量回归测试 |

**M-1 中指针运算 → string 方法的转换对照**：

| `char*` 指针运算 | `std::string` 替代 |
| --- | --- |
| `while(*p == ' ') p++;` | `size_t pos = s.find_first_not_of(' ');` |
| `p = strchr(s, '\n');` | `size_t pos = s.find('\n');` |
| `*p = '\0';` 截断 | `s.resize(pos);` 或 `s.substr(0, pos);` |
| `p + offset` 偏移访问 | `s[pos]` 或 `s.substr(pos);` |
| `char buf[N]; ... buf[idx]` | `s[idx]`（无变化） |
| `sscanf(s, "%d", &n)` | `std::stoi(s)` → 改用 `safe_stoi(s)` |

**M-1 中 FILE* → ifstream 的转换对照**：

| `FILE*` 操作 | `std::ifstream` 替代 |
| --- | --- |
| `FILE* fp = fopen(fname, "r");` | `std::ifstream ifs(fname);` |
| `fclose(fp);` | 不需要（析构函数自动关闭），或 `ifs.close();` |
| `fgets(buf, N, fp);` | `std::getline(ifs, line);`（读入 `std::string`） |
| `fscanf(fp, "%d", &n);` | `ifs >> n;`（需验证空白符处理一致性），或 `std::getline` + `safe_stoi` |
| `while (!feof(fp))` | `while (std::getline(ifs, line))` |
| `fread(buf, 1, N, fp);` | `ifs.read(buf, N);` |
| `pstream`（gzip 透明读取） | `redi::pstream` 兼容 ifstream 接口，直接替换 `std::ifstream` 即可 |

> **注意**：USalign 使用 `pstream.h`（第三方库）读取 `.gz` 压缩文件，其接口兼容 `std::istream`。替换时用 `redi::pstream` 替代 `std::ifstream` 即可保持 gzip 透明读取能力。

**涉及函数**（初步统计，执行时需确认）：
- `read_PDB`、`get_PDB_lines`、`output_results`、`extract_aln_from_resi`、`PrintErrorAndQuit` 等 `basic_fun.h` 中的核心函数
- `TMalign_main`、`MMalign_main`、`SOIalign_main` 等算法头文件中接受 `char*` 序列参数的函数
- 需特别关注有指针偏移操作的函数：如 PDB 解析中遍历行的 `char*` 指针、序列比对中的 `seqx[r1]` 索引（索引访问天然兼容，无需改动）
- 文件 I/O 函数：`get_PDB_lines`（内部 `fopen` → `ifstream`/`pstream`）、`file2chainlist`（读取列表文件）等

**预计步骤**：~11-13 步（M-1: 2 步——basic_fun.h + 算法头文件各 1 步，M-2: 7-9 步，M-3: 1 步，回归验证: 1 步）

### VLA 热点分析策略

> **VLA 替换为 `std::vector` 之前，必须先完成热点分析。** 热点 VLA 直接替换会导致每次调用触发堆 `malloc`/`free`，在百万次级循环中性能退化远超 20%。

#### 第一步：全局 VLA 扫描

使用 `-Wvla` 编译选项列出所有 VLA 位置：

```bash
g++ -O3 -ffast-math -lm -Wvla -Werror=vla -o USalign.exe USalign.cpp 2>&1 | grep "variable length"
```

将所有 VLA 位置记录到一个清单中（预计 ~15-20 处），包含文件名、行号、VLA 变量名和大小表达式。

#### 第二步：热点判定标准

对每个 VLA 位置，按以下规则判定是否为热点：

| 判定维度 | 热点 | 非热点 |
| --- | --- | --- |
| **调用频率** | 在 `for(chain_i...)` 或 `for(chain_j...)` 内层循环中 | 在函数入口、初始化阶段、文件解析时 |
| **所在函数** | `TMalign_main`、`Kabsch`、`NWDP_TM`、`score_fun8` 等核心算法 | `get_PDB_lines`、`read_PDB`、`print_*` 等 I/O 或工具函数 |
| **每次调用数组大小** | 随输入规模变化（如 `n_ali`、`xlen`），每次可能不同 | 固定小尺寸或仅调用一次 |
| **调用次数预估** | 运行一次测试用例可能被调用 >1000 次 | 运行一次测试用例调用 <10 次 |

**判定流程**：满足"调用频率"和"所在函数"任一条件即为热点；其余为非热点。不确定时默认标记为热点，保守处理。

#### 第三步：分类处理

**非热点 VLA → `std::vector`**：

```cpp
// 原始 VLA
int arr[n];

// 替换为
std::vector<int> arr(n);
```

**热点 VLA → `thread_local static std::vector` + `resize()` 复用**：

```cpp
// 原始 VLA（热点路径中）
double **tmp_xa;
NewArray(&tmp_xa, n_ali, 3);  // 每次迭代 malloc

// 替换为 —— 复用同一缓冲区，仅 grow 时分配
thread_local static std::vector<double> tmp_buf;
tmp_buf.resize(n_ali * 3);     // 只在需要更大容量时才重新分配
// ... 使用 tmp_buf.data() 或索引访问
```

关键点：`thread_local static` 确保跨调用复用，`resize()` 只在容量不足时触发分配。对于多线程不存在（USalign 是单线程程序），`static` 即可，但 `thread_local` 更安全。

**无法安全替换的热点 VLA → 保留不转换**：

如果 VLA 与 `NewArray`/`DeleteArray` 模板紧密耦合（如 `double **xa` 二维数组），且二维指针的整体迁移延后到性能优化阶段，则标记为"保留"，在清单中注明原因。

#### 第四步：验证

每完成一个文件的 VLA 替换后，运行性能回归测试：

```bash
cd scripts
python run_perf_test.py
```

- 若 `<20%` 变化 → 通过
- 若 `>=20%` 变化 → 该 VLA 标记为热点，回退到 `thread_local static vector` 方案或保留

**预计 VLA 热点分析步骤**：~3-4 步（扫描清单 1 步，L0-L1 文件替换 1 步，L2 文件替换 1-2 步，全局验证 1 步）

### printf 独立里程碑

> **前置条件**：第 0-4 层全部完成、char* → string 里程碑完成、VLA 热点分析完成，且所有回归测试通过后，再启动此里程碑。

#### 为什么把 printf 留到最后

`printf` 是格式化的 DSL（如 `"%5.2f"`），`std::cout` 是有状态的流操纵器（如 `std::fixed << std::setprecision(2) << std::setw(5)`）。两者在以下边界值下行为常常不一致：

| 场景 | `printf` 行为 | `cout` 行为 | 差异 |
| --- | --- | --- | --- |
| 浮点进位 `.995` → `%5.2f` | `" 1.00"`（进位后宽度可能变化） | `" 1.00"`（`setprecision` 同样进位，但舍入模式可能不同） | 极少数平台/值下不一致 |
| 负号占位 `%5.2f` 负数 | `"-1.00"`（负号占一个宽度） | `"-1.00"`（`setw` 计算整个字符串宽度，结果相同） | 基本一致 |
| `%6d` 对齐 `setw(6)` | 右对齐，空格填充 | 右对齐（默认），空格填充 | 一致 |
| `%04d` 零填充 | `"0001"` | 需 `setfill('0')` + `setw(4)`，且 `setfill` 是持久状态 | 必须手动恢复 `setfill(' ')` |
| `printf(".")` 纯文本 | 直接输出 | `cout << "."` 直接输出 | 完全一致 |

逐字节对齐的调试极其痛苦——因为回归测试按字节比对，一个空格差异就会 FAIL。为了对齐而写的 `cout` 代码往往比原始 `printf` 更冗长，违背"提升代码风格"的初衷。

#### 策略

将 printf 分为两类处理：

| 类别 | 示例 | 处理方式 |
| --- | --- | --- |
| **纯文本 printf**（无格式化占位符） | `printf("Usage: ...\n")` | 在第 0-4 层中**顺手替换**为 `std::cout << "Usage: ...\n"`，零风险 |
| **格式化 printf**（含 `%d`/`%f`/`%s` 等） | `printf("%5.2f", val)`、`output_results` 函数 | **全部保留到此里程碑集中处理** |

#### 格式化 printf 的处理方案

对格式化 printf，有两条路径可选：

**路径 A — snprintf 桥接**（推荐，零风险）：

```cpp
// 原始
printf("TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);

// 替换为
char buf[256];
snprintf(buf, sizeof(buf), "TM-score= %5.4f  (d0= %.3f)\n", TM1, d0);
std::cout << buf;
```

优点：格式字符串不变，输出语义 100% 一致，无需调试格式化差异。缺点：保留了 `char buf[N]` 和格式字符串，不算纯 C++。

**路径 B — 纯 cout 格式化**（可选，风险高）：

```cpp
// 替换为
std::cout << "TM-score= " << std::fixed << std::setprecision(4) << std::setw(5) << TM1
          << "  (d0= " << std::setprecision(3) << d0 << ")\n";
```

优点：纯 C++ 风格。缺点：必须与基线逐字节比对验证，状态操纵器（`setfill`、`setprecision`）是全局持久的，容易污染后续输出。

**推荐策略**：优先路径 A（snprintf 桥接），因为格式化 printf 的 C++ 等价写法本质上是把 DSL 展开为冗长的流操纵器链，可读性和维护性反而下降。`output_results` 等大型输出函数使用路径 A 可以极大降低风险。

**唯一例外**：如果某处只有 1-2 个简单的 `%d` 或 `%s`，且上下文没有全局操纵器状态风险，可以用路径 B——前提是逐字节验证通过。

#### 步骤计划

| 步骤 | 改动内容 | 预计文件数 |
| --- | --- | --- |
| P-1 | 识别所有格式化 printf：用 `grep -n 'printf.*%'` 扫描全部源码，分类为"纯文本"和"格式化" | 全部文件 |
| P-2 | 纯文本 printf → `std::cout`（顺手改，低风险） | 1-2 文件 |
| P-3 | `basic_fun.h` 中 `output_results` 等核心输出函数的 printf → snprintf + cout | 1 文件 |
| P-4 | `TMalign.h` 等算法头文件中的格式化 printf → snprintf + cout | 3-4 文件 |
| P-5 | L3 算法入口 cpp 文件中的格式化 printf → snprintf + cout | 3-4 文件 |
| P-6 | L4 主程序 + 工具 cpp 文件中的 printf → cout/snprintf | 3-4 文件 |
| P-7 | `fprintf(stderr, ...)` → `std::cerr`（无格式化内容）或 snprintf + cerr（有格式化） | 1-2 文件 |
| P-R | 全量回归测试 + 性能测试验证 | — |

**预计 printf 里程碑步骤**：~8-10 步

### 预计总计

- 第 0-4 层：约 **75-80 个步骤**
- 独立里程碑 char* → string + FILE* → ifstream：约 **11-13 个步骤**
- VLA 热点分析：约 **3-4 个步骤**
- printf 独立里程碑：约 **8-10 个步骤**
- 二级指针改造：~15 步延后到性能优化阶段
- 合计约 **97-107 个步骤**，每步改动量小、易审查、易回退

### 补充：MMalign.h 依赖的混合策略（2026-05-16）

> **背景**：执行 M-2（USalign.cpp 调用点迁移）时发现，`MMalign.h` 中的 `MMalign_search`/`MMalign_final`/`MMalign_iter` 等函数接收 `char* seqx, char* seqy, char* secx, char* secy, double** xa, double** ya` 参数，但**进入函数后立即用 `new[]`/`NewArray()` 覆盖，调用方传入的值完全不被读取**。这些函数是 USalign.cpp 中 MMalign() 多链路径、mTMalign()、flexalign()、SOIalign() 的阻塞依赖。

#### 核心发现：工作缓冲区反模式

`MMalign_search` 和 `MMalign_final` 的函数体模式：

```cpp
// 参数 char *seqx, double **xa 等进入后立即被覆盖
seqx = new char[xlen+1];    // 忽略调用方传入值
NewArray(&xa, xlen, 3);     // 同上
// ... 使用 ...
delete [] seqx;             // 自行释放
DeleteArray(&xa, xlen);
```

调用方传入的值（即使是 nullptr 或野指针）永远不会被解引用，只被覆盖。

#### 决策：绕过 MMalign.h，使用占位符隔离

**不修改 MMalign.h 任何函数签名**（避免重写 200 行核心算法 `MMalign_search` 的内部缓冲区管理逻辑）。在 USalign.cpp 调用方使用 `nullptr` 占位符传递：

```cpp
// MMalign() 函数级变量改为 string
string seqx, seqy;

// 多链循环内：string 直接用于 copy_chain_data/TMalign_main/se_main
copy_chain_data(..., seqx, secx);  // string 重载
TMalign_main(..., seqx.c_str(), ...);  // .c_str() 桥接

// 迭代优化调用：声明 nullptr 占位符
char *sx=nullptr, *sy=nullptr, *scx=nullptr, *scy=nullptr;
double **xa_buf=nullptr, **ya_buf=nullptr;
MMalign_iter(..., sx, sy, scx, scy, ...);  // 内部立即 new[] 覆盖
MMalign_final(..., sx, sy, scx, scy, ...); // 同上
// delete[] nullptr 是合法空操作，无需清理
```

#### USalign.cpp 剩余 M-2 细化步骤

| 步骤 | 函数 | 改动量 | 风险 | 说明 |
|------|------|--------|------|------|
| **A** | `MMalign()` 多链路径 + 迭代优化 | ~11 处 | 低 | 函数级 `string seqx, seqy;` + 删除 `new char[]` + `.c_str()` + nullptr 占位符 |
| **C** | `SOIalign()` | ~6 处 | 低 | `SOIalign_main` 已接受 `const char*`，接近 TMalign() 模式 |
| **D** | `flexalign()` | ~6 处 | 低 | 接近 TMalign() 模式 |

#### mTMalign() M-2 细化子步骤（2026-05-17）

> **背景**：mTMalign()（~1377 行，4 层嵌套循环）首次迁移失败——hinge 段（2183-2197 行）中 `seqy = new char[ylen+1]` + 逐字符 `seqy[r]=seqy_ext[r]` 改为 string 时，`operator[]` 写入超过 `size()` 的位置是未定义行为。**正确做法**：用 `seqy.assign(seqy_ext, ylen)` 一步完成 resize + 复制。

| 子步骤 | 范围 | 内容 | 改动量 | 风险 |
|--------|------|------|--------|------|
| **B-1** | Stage A（1757-1865） | 初始全对全矩阵：2 处 `seqx/seqy = new char[]` → `string seqx, seqy;`，`TMalign_main` 加 `.c_str()` | ~6 行 | 低 |
| **B-2** | Stage B 前半（1961-2089） | 迭代替换循环：2 处 `seqx/seqy = new char[]` → `string` | ~5 行 | 低 |
| **B-3** | Stage B hinge（2090-2221） | 恢复比对循环：4 处 `new char[]` → `string`；**关键修复**：`seqy[r]=seqy_ext[r]` → `seqy.assign(seqy_ext, ylen)` | ~5 行 | **关键** |
| **B-4** | Stage C（2267-2369） | 最终全对全：2 处 `seqx/seqy = new char[]` → `string` | ~3 行 | 低 |
| **B-5** | 清理（1722） | 移除集中声明 `char *seqx, *seqy;` | 1 行 | 零 |

每步独立编译、测试、提交。步骤间无依赖，可任意顺序执行。

**预计新增步骤**：原 4 步（A-D）+ mTMalign 5 子步（B-1~B-5）= **9 步**
**预计总计**：原 97-107 步 + 9 步 ≈ **106-116 步**

## Git 工作流

### 初始化

```bash
cd USalign
git checkout -b USalign-beta   # 从 master 创建本地分支
```

### 每个步骤的标准流程

```bash
# 1. 修改源码（1-2 个文件，一种 C 模式替换）

# 2. 编译验证
g++ -O3 -ffast-math -lm -o USalign.exe USalign.cpp
```

**3. 根据编译结果分两条路径**：

**路径 A — 编译失败**：
- 告知开发人员：哪个步骤、哪些文件、编译器报错信息
- 与开发人员一起定位根因并修复
- 修复后重新编译，直至编译通过
- 编译通过后执行路径 B 的测试流程（见下方），不可跳过测试直接提交
- 问题和解决方案记录在 commit message 中

**路径 B — 编译通过**：
- 输出本次修改摘要（修改了哪些文件、替换了多少处 C 风格 → C++ 风格）
- 告知开发人员：编译已通过，请手动执行测试用例验证
- **开发人员手动执行**（不自动运行）：
  ```bash
  cd scripts
  python run_regression.py   # 14 个功能测试用例
  python run_perf_test.py    # 4 个性能测试用例
  ```
- 开发人员检查测试结果（14 功能全部 PASS，4 性能 < 20% 变化）并回复确认
- **测试未通过**：在当前步骤内定位问题、修复、重新编译、重新提交开发人员测试，不得进入下一步
- **测试通过后**，由开发人员/助手执行提交：

```bash
# 提交
cd ../USalign
git add -A
git commit -m "refactor(<层-步>): <简短描述>"
```

> **注意**：测试脚本由开发人员手动运行，而非助手自动执行。原因是：(1) 确保开发人员亲眼看到测试结果；(2) 性能测试（特别是 database_search 约需 3 分钟）需要开发人员知晓等待时间；(3) 测试失败时开发人员可以立即介入排查，而非事后追溯。

### Commit 消息格式

```
refactor(<层-步>): <简短描述>

- 将 N 处 <C模式> 替换为 <C++模式>
- 涉及文件: <文件列表>
```

示例：
```
refactor(L0-3): BLOSUM.h 将 #define 替换为 constexpr 和 #pragma once

- BLOSUM.h: 头文件保护改用 #pragma once
- BLOSUM.h: 氨基酸字母表宏 AAlist 改为 constexpr std::array
- NULL → nullptr（BLOSUM.h 中 N 处）
```

### 测试失败时的处理

1. 在当前步骤内修复问题
2. 修复后重新测试，PASS 后 commit
3. 不允许回退到上一步——保证问题只在当前步骤内排查

### 全部完成后

```bash
# 选项：合并为单个 commit 后推到 master
git checkout master
git merge --squash USalign-beta
git commit -m "refactor: 将全部 C 风格代码替换为 C++ 风格

共修改 28 个文件，涵盖编码风格和语法风格两个层面：

编码风格（库函数/API）：
- NULL → nullptr
- C 头文件 → C++ 头文件
- printf/sprintf → std::cout/snprintf+cout（独立里程碑，格式化 printf 用 snprintf 桥接确保逐字节一致）
- strcmp/strlen/strcpy → std::string 方法
- atoi/atof → safe_stoi/safe_stod（双重重载：const char* 版用 strtol/strtod 零分配，string& 版用 stoi/stod+try-catch）
- char* → std::string/std::string_view + FILE* → std::ifstream（独立里程碑，反向桥接：string+ifstream 版为真正实现，char*+FILE* 版退化为薄包装器）
- C 风格转换 → static_cast
- clock() → std::clock()（仅加 std:: 前缀，不改计时方式）
- #define 宏 → constexpr / #pragma once
- using namespace std; 从所有头文件移除 → 头文件中显式 std:: 前缀，.cpp 文件中保留 using-directive
- char msg[N] → std::string

语法风格（语言结构）：
- VLA 可变长数组 → std::vector（非热点）/ thread_local static vector 复用（热点）/ 保留（无法安全替换的热点）
- C 块注释 → // 行注释
- 循环外声明变量 → 循环内声明
- (char*) 强制转换 → 直接使用 string
- 逗号声明合并 → 每行独立声明
- 函数入口集中声明 → 随用随声明"
git push origin master
```

## 验证策略

### 功能回归测试

```bash
cd scripts
python run_regression.py
```

- 14 个功能测试用例覆盖：标准蛋白比对、多链拆分、寡聚体、循环置换、非顺序比对、叠加结构输出、TM-score 评估、复合物链 ID、链映射、RNA 多结构比对、全对全比对、数据库搜索
- 标准：所有用例 PASS（baseline 和 current 逐字节一致）

### 性能回归测试

```bash
cd scripts
python run_perf_test.py
```

- 4 个性能测试用例各运行 5 次取平均
- 标准：所有用例 < 20% 变化，不能出现 FAIL

### 编译验证

每步修改后的源码必须成功编译：
```bash
g++ -O3 -ffast-math -lm -o USalign.exe USalign.cpp
```

## 风险控制

| 风险 | 应对措施 |
| --- | --- |
| `printf` 格式转换 `cout` 输出不一致（**高风险**） | `printf` 是格式化 DSL，`cout` 是有状态流操纵器。`%5.2f` vs `fixed`+`setprecision(2)`+`setw(5)` 在进位、负号占位、宽度截断等边界值下行为常常不一致。逐字节对齐的调试成本极高，且最终的 `cout` 代码可能比原始 `printf` 更丑陋，违背重构初衷。**应对**：`printf`/`sprintf` 全部延后到最后独立里程碑集中处理，不在第 0-4 层执行。无格式的纯文本 `cout << "..."` 可在各层顺手改，不涉及格式化风险。独立里程碑中的策略见"printf 独立里程碑"章节 |
| `atoi/atof` → `stoi/stod` 抛异常 + 隐式 string 构造开销（**高风险**） | (1) **异常风险**：`atoi("abc")` 静默返回 0，`std::stoi("abc")` 抛出 `std::invalid_argument`。(2) **隐式构造开销**：若 `safe_stoi` 仅接受 `const std::string&`，调用方传 `const char*` 时触发隐式 `std::string` 构造（malloc+copy+free），在 PDB 解析循环中累积开销不可忽略。**应对**：`safe_stoi`/`safe_stod` 必须提供**双重重载**——`const char*` 版本内部用 `strtol`/`strtod`（零分配，行为与 `atoi`/`atof` 一致），`const std::string&` 版本用 `std::stoi`/`std::stod` + try-catch。编译器根据实参类型自动选择最优版本，调用方无需改动 |
| `char*` → `string` 空指针 | 原传 `NULL` 处改为 `""` 或 `std::optional`。此问题在独立里程碑中处理 |
| `NULL` → `nullptr` 整型上下文编译失败（**高风险**） | C 中 `NULL` 通常定义为 `((void*)0)` 或 `0`，可隐式转换为整型。`nullptr` 是 `std::nullptr_t` 类型，**只能隐式转换为指针类型，不能转换为整型**。若 `NULL` 出现在整型上下文（如 `int x = NULL;`、`if (some_int == NULL)`、`func(NULL)` 其中形参为 `int`），直接替换为 `nullptr` 将编译失败。**应对**：(1) 每次 NULL 替换前，先 `grep -n '\bNULL\b'` 列出所有出现位置；(2) 逐处按以下规则判定——赋值目标/比较对象/函数参数是指针类型 → `nullptr`，是整型 → `0`，无法判定时保留 `NULL` 并在 commit 中注明；(3) 常见安全模式：`FILE* fp = NULL` → `nullptr`、`int* p = NULL` → `nullptr`、`NewArray(&xa, ...)` 前 `xa=NULL` → `xa=nullptr`；常见陷阱模式：`int ret = NULL` → 改为 `int ret = 0` |
| `clock()` → `chrono` 语义不同（**严重**） | `clock()` 测量 **CPU 时间**，`std::chrono::steady_clock` 测量**墙上时间**。两者语义不同，替换会破坏性能测试框架（基线值将不可比）。**本次不做此替换**，仅将 `clock()` 写为 `std::clock()` 即可（已在 `<ctime>` 中） |
| VLA → `vector` 性能退化（**高风险**） | VLA 在栈上分配（O(1) 开销），`std::vector` 在堆上 `malloc`/`free`。若 VLA 位于热点循环（如 `TMalign_main` 内层 `for(chain_j...)`）内部，每次迭代都触发堆分配/释放，性能退化可能远超 20%。**应对**：(1) 先用 `-Wvla` + `-Werror=vla` 编译选项全局扫描，列出所有 VLA 位置；(2) 按"VLA 热点分析策略"逐位置标注热点/非热点；(3) 非热点安全替换为 `std::vector`；(4) 热点采用 `thread_local static std::vector<T> buf; buf.resize(n);` 复用同一缓冲区，或保留 VLA 不转换。详见"VLA 热点分析策略"章节 |
| `char*` → `std::string` 级联影响（**高风险**） | `basic_fun.h` 被全项目所有文件 include，函数签名变更会导致所有调用点（~20 个文件）级联修改。**已作为独立里程碑处理**（见上文），采用**反向桥接**策略：M-1 先写 string 版的真正实现（用 `find`/`substr`/`operator[]` 替代指针运算），char* 版退化为薄包装器；M-2 逐文件迁移调用点；M-3 删除包装器。指针运算改造集中在 M-1，避免推到 M-3 集中爆发 |
| `FILE*` → `ifstream` 级联影响（**高风险**） | 与 char* 问题同源：`get_PDB_lines` 等核心函数内部使用 `FILE*`/`fopen`/`fgets`，若在 L1-6 单独改造，函数签名变更同样导致所有调用点编译失败。**已合并到 char* → string 独立里程碑**（见上文），在 M-1 重写实现时顺手将 `fopen`→`ifstream`/`pstream`、`fgets`→`std::getline`、`fscanf`→`>>`。FILE* 若是函数参数则随签名一起改，若是局部变量则纯实现替换。薄包装器（char* 版本）内部先 `fopen` 读取内容转 string，再调 string 重载，因此旧调用点无感 |
| `using namespace std;` 在头文件中污染全局命名空间（**高风险**） | `basic_fun.h` 等头文件中的 `using namespace std;` 是严重的 C++ 反模式：所有 include 该头文件的编译单元被强制注入 `std` 命名空间。未来若引入与 `std` 同名的自定义符号（如 `distance`、`count`、`find`、`hash`），将产生诡异的名称冲突编译错误，且排查极其困难。**应对**：(1) 从所有头文件中移除 `using namespace std;`；(2) 对头文件中所有 std 库标识符（`cout`、`cerr`、`endl`、`string`、`vector`、`map`、`ifstream`、`max`、`min`、`swap`、`pair` 等）添加 `std::` 前缀；(3) 编译 → 编译器报出所有遗漏的未限定标识符 → 逐一补 `std::` → 重新编译直至零错误；(4) `.cpp` 文件中的 `using namespace std;` 保留（作用域局域化，影响可控）。**注意**：`basic_fun.h` 被全项目 include，移除其 using-directive 后编译错误将级联到所有文件，但每个错误都是机械修复（加 `std::` 前缀），无语义变化风险 |
| `#define` 宏 → `constexpr` 预处理依赖 | `#define` 宏可被 `#ifdef`/`#ifndef` 等预处理条件引用，`constexpr` 变量不能。替换前必须确认宏仅用于运行时、未被预处理指令引用。BLOSUM.h 中的字母表常量宏需逐一检查 |
| `#pragma once` 在 Windows 下的风险 | Windows 文件系统大小写不敏感，`#pragma once` 对同一文件的路径变体（如 `Kabsch.h` vs `kabsch.h`）会正确识别为同一文件，因此在 Windows 上 `#pragma once` 实际比 `#define` 保护更安全。本项目仅在 Windows 下编译使用，可放心替换 |
| 测试时间成本 | 每步需运行 14 功能测试 + 4×5=20 次性能测试（database_search 性能测试约需 3 分钟）。按 ~100 步计，净测试时间约 **8-12 小时**。建议：低风险步骤（如注释转换）可批量合并以减少测试轮次 |
| 块注释 `/* */` → `//` 结构混乱 | 仅转换单行短注释；多行长文本保留 `/* */` |
| `double **` / `int **` → `vector` 性能和接口变更 | **本次不做，延后到性能优化阶段**。原因：(1) ~347 处修改量大但语法收益有限（当前 `NewArray` 分配的 `double**` 与 `vector<vector<T>>` 内存布局几乎相同，均为碎片化堆分配）；(2) 真正的优化应改为 `vector<array<double,3>>` 获得连续内存布局，这超出了纯风格重构范围。届时热点路径（Kabsch、TMscore）保留指针形式传参 |

### M-3 详细执行方案（2026-05-18 分析制定）

> **核心原则**：所有修改**仅做语法和编码风格上的重构**，不改变任何源码语句的**语义**（即程序行为）。每步改动必须保证：同样的输入产生同样的输出，同样的计算产生同样的结果。违反此原则的修改（如改动算法参数、改变函数行为、调整数据结构语义）一律禁止。

#### 前置状态分析

M-1（桥接）和 M-2（调用点迁移）已全部完成。当前剩余 char* 包装器及其调用者分布：

**`read_PDB` char* 包装器**（basic_fun.h:819-826，反向桥接）：

```
char* 包装器（strcpy 拷回）
  └── 唯一剩余调用者：MMalign.h:1141 parse_chain_list
        └── seq = new char[len+1] → 传 char* 给 read_PDB
```

**`copy_chain_data` char* 包装器**（MMalign.h:695-702，反向桥接）：

```
char* 包装器（strcpy 拷回）
  └── ~7 个调用者，全部在 MMalign.h 内部：
        ├── MMalign_search (line 1349, 1373)
        ├── MMalign_final (line 1601, 1619)
        ├── MMalign_iter (line 1843, 1861)
        ├── MMalign_dimer (line 3131, 3155)
        └── copy_chain_pair_data 也被这些函数调用，签名含 char* seqx, char* seqy
```

**`se_main` string 重载**（se.h:9-30，正向桥接——非 M-3 删除对象）：

```
string 重载（一行 .c_str() 转发）
  → char* 版本（真正的实现，238 行）
```

**`NWalign_main` string 重载**（NWalign.h:384-390，正向桥接——非 M-3 删除对象）：

```
string 重载（一行 .c_str() 转发）
  → char* 版本（真正的实现，~55 行）
```

#### 问题 15：se_main 跨作用域崩溃

**症状**：mTMalign B-3（hinge 恢复循环）和 Stage C（最终全对全）中，seqy 声明在外层 `for(iter)` 作用域，seqx 声明在内层 `for(tm_idx)` 作用域。调用 `se_main(xa, ya, seqx, seqy, ...)` 匹配 string 重载时**程序直接崩溃**。显式传 `.c_str()` 绕过 string 重载则一切正常。

**已验证的事实**：
- B-1/B-2 中 seqx/seqy 同在 inner-most 作用域 → string 重载正常
- 同作用域内 string 重载也正常（USalign.cpp:413/704/897 的 se_main 调用）
- `.c_str()` 显式传递可 100% 规避
- `se_main` 函数体极长（238 行），大量局部变量，栈帧很大

**源码分析**：string 重载的语义等价性已确认——`se_main(xa, ya, seqx.c_str(), seqy.c_str(), ...)` 与在调用处手动写 `.c_str()` 在 C++ 标准层面语义完全等价。`.c_str()` 返回的 `const char*` 临时量在 `se_main` 调用表达式结束前均有效。

**推测根因**：GCC/MinGW 的优化 Bug——单行 inline 函数 + 跨栈帧 string 引用 + `.c_str()` 的组合触发了编译器错误优化。或与 se_main 栈帧接近极限有关（mTMalign 深层嵌套循环中栈空间紧张，inline 改变栈布局后溢出）。

**当前处置**：所有跨作用域调用点使用 `.c_str()` 显式传递。此问题标记为 P0，但**不阻塞 M-3**——因为 se_main 的 char* 版本是真正实现，string 重载并非 M-3 的删除目标。

**后续计划**（阶段 C，独立于 M-3）：
1. 用 `-O0` 编译验证是否为优化 Bug
2. 若确认 → 给 string 重载加 `__attribute__((noinline))` 修复
3. 修复后移除所有 `.c_str()` 绕过代码

#### M-3 执行方案

M-3 的真正目标：删除 `read_PDB` char* 包装器和 `copy_chain_data` char* 包装器。拆为两个独立阶段。

##### 阶段 A：删除 `read_PDB` char* 包装器（3 步）

| 步骤 | 内容 | 文件 | 风险 |
|------|------|------|------|
| **A-1** | `parse_chain_list` 中 `seq = new char[len+1]` → `std::string seq`；`read_PDB` 直接调 string 重载；`seq[r]` 索引访问不变；`make_sec` 调用加 `.c_str()` | MMalign.h | 低 |
| **A-2** | 删除 `basic_fun.h:819-826` 的 `read_PDB` char* 包装器 | basic_fun.h | 低 |
| **A-3** | 回归测试 | — | — |

##### 阶段 B：删除 `copy_chain_data` char* 包装器（6 步）

| 步骤 | 内容 | 文件 | 风险 |
|------|------|------|------|
| **B-1** | `copy_chain_pair_data` 签名 `char *seqx, char *seqy` → `std::string &seqx, std::string &seqy`；`seqx[xlen]=...` 逐字符赋值 → `seqx += ...`（string append）；`seqx[xlen]=0` 空终止 → 删除（string 自动管理）；`xlen++/ylen++` 手动计数 → 用 `seqx.size()`/`seqy.size()` | MMalign.h | 中 |
| **B-2** | `MMalign_search`：`seqx/seqy = new char[xlen+1]` → `std::string seqx, seqy; seqx.reserve(xlen); seqy.reserve(ylen);`；`delete[] seqx/seqy` → 删除；`TMalign_main(..., seqx, seqy, ...)` → `TMalign_main(..., seqx.c_str(), seqy.c_str(), ...)` | MMalign.h | 中 |
| **B-3** | `MMalign_final`：同上模式 | MMalign.h | 中 |
| **B-4** | `MMalign_iter`：同上模式（若与 search/final 共用代码路径，需同步改动） | MMalign.h | 中 |
| **B-5** | 删除 `copy_chain_data` char* 包装器（MMalign.h:695-702） | MMalign.h | 低 |
| **B-6** | 全量回归测试 | — | — |

##### 阶段 C：se_main / NWalign_main 方向翻转（后续，可选）

> **前置条件**：问题 15 已修复，阶段 A/B 已完成且稳定。

| 步骤 | 内容 |
|------|------|
| **C-1** | `se_main` char* 版函数体重写为接受 `const std::string&`，内部 `seqx[i]` 索引操作不变（string `operator[]` 语义等价） |
| **C-2** | 原 char* 版改为包装器：`std::string sx(seqx), sy(seqy); return se_main(..., sx, sy, ...);` |
| **C-3** | `NWalign_main` char* 版函数体重写为接受 `const std::string&`；`trace_back_gotoh`/`trace_back_sw` 调用加 `.c_str()`（这些子函数内部有 `strncpy` 指针运算，不在此次改造范围） |
| **C-4** | 原 char* 版改为包装器 |

#### M-3 关键转换对照

以下是在 M-3 步骤中涉及的具体代码转换模式，严格遵循语义不变原则：

| # | 原代码（C 风格） | 替换为（C++ 风格） | 语义验证 |
|---|---|---|---|
| 1 | `seq = new char[len+1]` | `std::string seq; seq.reserve(len)` | 分配缓冲区 → 分配 string 容量 |
| 2 | `read_PDB(..., seq, ...)` 调 char* 重载 | `read_PDB(..., seq, ...)` 调 string 重载 | 相同函数名，编译器选择 string 重载，行为一致 |
| 3 | `seqx[xlen]=seqx_vec[i][r]; xlen++` | `seqx += seqx_vec[i][r]` | 逐字符追加 → string append，`size()` 自动递增 |
| 4 | `seqx[xlen]=0` | （删除） | C 字符串终止符 → string 无需手动终止 |
| 5 | `delete[] seqx` | （删除） | 手动释放 → string 析构自动释放 |
| 6 | `TMalign_main(..., seqx, seqy, ...)` 其中 seqx/seqy 为 char* | `TMalign_main(..., seqx.c_str(), seqy.c_str(), ...)` | TMalign_main 接受 `const char*`，`.c_str()` 桥接 |
| 7 | `make_sec(seq, xa, len, sec, ...)` 其中 seq 为 char* | `make_sec(seq.c_str(), xa, len, sec, ...)` | make_sec 接受 `const char*`，`.c_str()` 桥接 |
| 8 | `seq[r]` 读取单个字符 | `seq[r]`（不变） | string 和 char* 的 `operator[]` 语义等价 |
| 9 | `strcpy(seq, seq_str.c_str())`（包装器内部） | 整段删除 | 调用方已直接传 string，无需拷回 char* |

### secx/secy 迁移：二级结构数组 char* → std::string（2026-05-18 制定）

> **核心原则**：所有修改仅做语法和编码风格上的重构，不改变任何源码语句的语义。

#### 背景

`secx`/`secy` 是二级结构赋值数组，每个字符表示一个残基的二级结构类型（H=α螺旋, E=β折叠, C=线圈等）。当前全部使用 `char*` + `new char[]`/`delete[]` 管理内存，属于 C 风格，应统一转换为 `std::string`。

与 `seqx`/`seqy` 不同，`secx`/`secy` 由 `make_sec()` 函数填充（直接写入 `sec[i]='C'` 后 `sec[len]=0`），而非通过 `copy_chain_data` 等已有 string 重载的工具函数。

#### 转换策略

不新增 `make_sec` 的 string 重载。利用 `std::string::resize()` + `&sec[0]`（C++11 起 `std::string` 内部缓冲区连续且可写）：

```cpp
// 旧代码：
secx = new char[xlen+1];
make_sec(xa, xlen, secx);           // 写入 char*
TMalign_main(..., secx, ...);       // 读取 const char*
cout << secx << endl;               // 作为 C 字符串输出
delete[] secx;

// 新代码：
std::string secx;
secx.resize(xlen+1);                // 分配 len+1 字节可写缓冲区
make_sec(xa, xlen, &secx[0]);       // 写入 &sec[0]（char*，C++11 保证连续可写）
TMalign_main(..., secx.c_str(), ...); // 读取 .c_str()（const char*）
cout << secx.c_str() << endl;       // .c_str() 确保与旧 C 字符串输出一致
// 自动析构，无需 delete[]
```

**注意**：经过 `make_sec` 写入后，string 的 `.size()` 仍为 `len+1`，末尾字节为 `'\0'`。所有输出点必须用 `.c_str()` 而非直接 `<< secx`，否则会多输出末尾的 `'\0'` 字符导致回归测试 FAIL。

#### 原子化步骤（17 步）

| 步骤 | 文件 | 函数/范围 | sec 分配 | 风险 | 说明 |
|------|------|----------|---------|------|------|
| S1 | `pdb2ss.cpp` | main 循环 | 1 | 低 | 最简单，验证转换模式 |
| S2 | `TMalign.cpp` | main 循环 | 2 | 低 | |
| S3 | `HwRMSD.cpp` | main 循环 | 2 | 低 | |
| S4 | `MMalign.cpp` | 单链路径 | 2 | 低 | 逐对分配 |
| S5 | `MMalign.cpp` | 全对全路径 | 2 | 低 | 循环内分配 |
| S6 | `MMalign.h` | `MMalign_search` | 4 | 中 | 参数重命名 `_arg` + 局部 string |
| S7 | `MMalign.h` | `MMalign_final` | 4 | 中 | 同上 |
| S8 | `MMalign.h` | `MMalign_se_final` | 4 | 中 | 同上 |
| S9 | `MMalign.h` | `MMalign_dimer` | 4 | 中 | 同上 |
| S10 | `USalign.cpp` | `TMalign()` | 2 | 低 | |
| S11 | `USalign.cpp` | `MMalign()` | 4 | 中 | 多链 + 全对全 |
| S12 | `USalign.cpp` | `SOIalign()` | 2 | 低 | |
| S13 | `USalign.cpp` | `flexalign()` | 4 | 中 | |
| S14 | `USalign.cpp` | `mTMalign()` | 8 | 中 | 多阶段，最复杂 |
| S15 | `USalign.cpp` | `MMdock()` | 4 | 低 | |
| S16 | `USalign.cpp` | `xyz_sfetch` / 数据库搜索 | 4 | 低 | |
| S17 | `flexalign.h` | `round2` + `hinge` 块 | 4 | 低 | 局部变量 `secx_h`/`secy_h` |

每步独立编译、测试、提交。步骤间无依赖，可任意顺序执行。

## 不修改的内容

- 第三方库 `pstream.h`
- 预编译二进制文件
- 测试框架脚本（`scripts/` 下的 Python 文件）
- Makefile
- 功能逻辑、算法参数、输出格式约定
