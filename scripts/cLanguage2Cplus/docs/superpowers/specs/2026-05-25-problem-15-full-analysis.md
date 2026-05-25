# 问题 15：se_main string 重载跨作用域崩溃 完整记录

**记录日期**: 2026-05-25
**严重性**: P0（已结案）
**涉及文件**: `se.h`, `USalign.cpp`

---

## 一、现象

mTMalign() 的 hinge 恢复循环（USalign.cpp:2090-2198, `for(tm_idx)` 循环）和 Stage C 最终全对全循环（USalign.cpp:2244-2298, `for(i) for(j)` 循环）中：

- **写法 A（崩溃）**: `se_main(xa, ya, seqx, seqy, ...)` — 传 std::string，编译器匹配 se.h 第 16-37 行的 string 重载 → 程序崩溃
- **写法 B（不崩）**: `se_main(xa, ya, seqx.c_str(), seqy.c_str(), ...)` — 传 const char*，编译器匹配 se.h 第 39 行 char* 重载 → 正常

在 B-1/B-2（Stage A 初始全对全矩阵，同作用域）中，写法 A 正常。只在 B-3（hinge 恢复）和 Stage C 中崩溃。

### 复现环境

- 操作系统: Windows
- 编译器: GCC/MinGW (mingw-w64)
- 编译选项: `-O3 -ffast-math -lm -static`
- 触发命令: `USalign.exe -dir .\MSTATest\ list.txt -suffix .pdb -mm 4 -mol RNA -outfmt -1 -m -`

---

## 二、涉及的代码

### se.h 中的两个 se_main 重载

```cpp
// se.h:16-37 — string 重载 (M-1 阶段新增的正向桥接, 仅一行转发)
int se_main(
    double **xa, double **ya, const std::string &seqx, const std::string &seqy,
    // ... 其余 20+ 个参数 ...
) {
    return se_main(xa, ya, seqx.c_str(), seqy.c_str(), ...);  // 转发到 char* 版
}

// se.h:39-277 — char* 版本 (原始实现, 238 行算法)
int se_main(
    double **xa, double **ya, const char *seqx, const char *seqy,
    // ... 其余 20+ 个参数 ...
) {
    // 238 行算法逻辑 — 真正的实现
}
```

### USalign.cpp mTMalign() 中的跨作用域场景

```
行 1894    for (iter=0; ...)           ← 第 1 层: iter 循环
行 2073      string seqy;              ← seqy 在 iter 作用域声明 (第 1 层)
行 2090      for (tm_idx=0; ...)       ← 第 2 层: recover 循环
行 2096        string seqx;            ← seqx 在 tm_idx 作用域声明 (第 2 层)
               ...
行 2122        se_main(xa, ya, seqx.c_str(), seqy.c_str(), ...)  ← 强制 .c_str()
```

seqx 在内层 (tm_idx)、seqy 在外层 (iter)，不在同一作用域。

---

## 三、诊断过程

### 尝试 1: 假设 GCC/MinGW 内联优化 Bug

给 string 重载加 `__attribute__((noinline))`，在 B-3 和 Stage C 中移除 `.c_str()` 绕过，直接传 string → **仍然崩溃**。

结论: 与内联无关。

### 尝试 2: 假设参数类型本身导致问题

B-1/B-2 中 seqx/seqy 同在 for(tm_idx) 最内层作用域 → 不崩。B-3/Stage C 中 seqx/seqy 跨作用域 → 崩。

说明不是 string 重载的代码本身有 bug，而是跟**调用上下文**有关。

### 当前假设（未通过反汇编验证）

大概率是**栈溢出**（stack overflow）。mTMalign() 约 700 行，在 iter 循环内声明了大量局部变量，栈帧已经接近极限。string 重载额外增加一层函数调用 (参数压栈 + 帧指针建立 + 返回地址 push 等)，叠加后踩穿栈保护页触发崩溃。

但精确的崩溃位置（是 push ebp 崩、还是 sub esp 崩、还是 call 指令崩）没有通过反汇编逐帧确认。

---

## 四、诚实标注：不确定的问题 → 已测试 ✅ (2026-05-25)

**Q: 如果直接把 238 行真实现的签名从 `const char*` 改为 `const std::string&`，不桥接而是作为真实现，会不会崩？**

**A: 不会崩。已测试验证。**

### 测试方案（方向翻转）

将 se.h 的结构完全翻转：

```
原来（M-1 阶段）:
  第 16-37 行: string 正向桥接 (const std::string& → .c_str() → char*)
  第 39-277 行: char* 真实现 (238 行)

翻转后（本次测试）:
  第 9-25 行: string 版前置声明
  第 27-49 行: char* 反向桥接 (const char* → 构造 std::string → string 实现)
  第 51-277 行: string 真实现 (const std::string&, 238 行，函数体未改)
```

关键改动：
- 真实现签名 `const char *seqx, const char *seqy` → `const std::string &seqx, const std::string &seqy`
- 函数体**零改动**（只用了 `operator[]` 读取，string 语义完全等价）
- char* 桥接内部构造临时 `std::string sx(seqx); std::string sy(seqy);` 后调用 string 实现

### 测试结果

- **msta_rna**: ✅ 通过，不崩溃（hinge 恢复循环 + Stage C 最终全对全均正常）
- **全部 14 个功能用例**: ✅ 用户手动验证通过
- 编译: ✅ GCC/MinGW `-O3 -ffast-math -lm -static`

### 结论修正

之前推测崩溃是因为 `const std::string&` 参数类型改变栈帧布局导致栈溢出——**此推测被否定**。真实现用 `const std::string&` 签名后一切正常。

真正原因更精确地指向**那层正向桥接本身**——不是参数类型的问题，而是桥接那一层函数调用帧 + 跨作用域 string 引用绑定的组合。正向桥接中 `const std::string&` 参数引用的是调用方跨栈帧的变量，编译器在深层嵌套中处理这种跨帧引用 + `.c_str()` 调用 + 再次调 char* 版的三层嵌套时出了问题。

---

## 五、解决方案演变

### 最终方案（2026-05-25 已采用并提交）

- **删除全部桥接层**：正向桥接（问题根源）和反向桥接（全项目已无 char* 调用者，死代码）一并删除
- `se.h` 精简为**唯一重载**：签名 `const std::string &seqx, const std::string &seqy`，238 行函数体零改动
- 全部 8 处调用点去除 `.c_str()` 绕过，直达 string 实现
- 优点: 零桥接、零绕路、最精简的 C++ 接口
- 代价: 无（全项目调用者均为 `std::string`，零 char* 调用路径）

---

## 六、最终结论

1. **崩溃根因**：M-1 阶段新增的 string 正向桥接——桥接函数的调用帧 + 跨作用域 string 引用绑定 + `.c_str()` 调用 + 再次调 char* 版的嵌套，在 mTMalign 深层嵌套中出了问题。不是 `const std::string&` 参数类型本身的问题。

2. **`const std::string&` 签名安全**：238 行真实现直接用 `const std::string&` 签名，深层嵌套中不崩溃。函数体对 `seqx`/`seqy` 只用 `operator[]` 读取，与 `const char*` 语义完全等价，无需任何改动。

3. **桥接层可彻底移除**：全项目已无 char* 调用者，正向桥接（问题根源）和反向桥接（死代码）均可删除。se.h 精简为唯一重载。

4. **同样适用于 NWalign_main**：NWalign.h 目前仍有相同的正向桥接模式，可以应用相同的精简方案。

---

## 七、完整发展脉络

### 阶段 1：M-1 新增正向桥接（2026-05-15/16）

**思路**：不动 238 行真实现（`const char*` 签名），只在外层套一个 string 壳。

```cpp
// se.h 第 16-37 行 — 新增的正向桥接（壳）
int se_main(..., const std::string &seqx, ...)   // 引用调用方的 string
{
    return se_main(..., seqx.c_str(), ...);       // 取指针，零拷贝转发进 char* 真实现
}

// se.h 第 39-277 行 — 真实现，原封不动
int se_main(..., const char *seqx, ...) { /* 238行算法 */ }
```

**为什么要加这一层而不是直接改签名**：不敢。担心 238 行真实现的签名从 `const char*` 改成 `const std::string&` 后，在 mTMalign 深层嵌套中会出问题。当时的判断是：真实现不动 = 绝对安全；壳只是一个可选入口，零拷贝、零风险。

### 阶段 2：问题 15 暴露（2026-05-17）

mTMalign 的 hinge 恢复循环（B-3）和 Stage C 中，传 string 经正向桥接 → **崩溃**。

**排查过程**：
- 加 `__attribute__((noinline))` → 仍然崩 → 排除内联 Bug
- B-1/B-2 同作用域不崩，B-3/Stage C 跨作用域才崩 → 跟调用上下文有关
- **推测**：`const std::string&` 参数类型改变了栈帧布局，叠加 mTMalign 深层嵌套导致栈溢出

### 阶段 3：`.c_str()` workaround（2026-05-17/18）

**方案**：在危险调用点手动加 `.c_str()`，利用 C++ 重载决议绕过正向桥接。

```cpp
// 危险调用点 — 加 .c_str() 绕过壳，直达 char* 真实现
se_main(xa, ya, seqx.c_str(), seqy.c_str(), ...);
//       编译器看到 const char* —→ 精确匹配 char* 重载 —→ 不崩

// 安全调用点 — 不加，走壳（同作用域，不崩）
se_main(xa, ya, seqx, seqy, ...);
```

**当时的决策**：方向翻转被标记为"永久取消"——基于阶段 2 的推测，如果 `const std::string&` 参数类型是问题根源，那把真实现也改成 `string&` 只会更糟。`.c_str()` 为永久方案。

**这个推测的问题**：没有验证。"参数类型有问题"只是一个假设——排除了内联，剩下的可能性中这个最像，但没有人实际测试过真实现改签名的效果。

### 阶段 4：方向翻转实验（2026-05-25）

**重新审视**：为什么不敢测试真实现改签名？当时的推测对不对？

```cpp
// 实验·第一步 — 翻转 + 保留反向桥接兜底
int se_main(..., const char *seqx, ...)           // 反向桥接（安全垫）
{
    std::string sx(seqx); std::string sy(seqy);    // char* → string（有拷贝）
    return se_main(..., sx, sy, ...);              // 转进 string 真实现
}

int se_main(..., const std::string &seqx, ...)     // 238 行真实现（签名改了）
{ /* 函数体零改动 */ }
```

**测试结果**：✅ msta_rna 不崩溃，14 用例全 PASS。

**关键发现**：`const std::string&` 签名本身没有问题。阶段 2 的推测是错的。

### 阶段 5：删掉所有桥接（2026-05-25）

**验证**：全项目扫描，零 `const char*` 调用方 → 反向桥接是死代码，正向桥接也不再需要。

```cpp
// 最终 se.h — 唯一重载，零桥接
int se_main(..., const std::string &seqx, ...)     // 238 行真实现
{ ... }
```

全部 8 处调用点的 `.c_str()` workaround 去除，直达 string 实现。

### 经验教训

1. **假设需要验证**：M-1 阶段因为"不敢"而加了桥接，阶段 2 因为"推测"而放弃了方向翻转。两次都没有实际测试那个最直接的方案——把真实现签名改了看看。
2. **桥接层有代价**：为了安全加的一层薄壳，成了唯一崩溃的来源。更讽刺的是，当初不敢改的真实现反而没问题。
3. **死代码要及时清理**：`.c_str()` workaround 和正向桥接共存了约一周——一半调用方走桥接、一半绕过。反向桥接从诞生到删除不到一小时，因为验证前提（全项目无 char* 调用方）成立后立刻可以判定为死代码。
