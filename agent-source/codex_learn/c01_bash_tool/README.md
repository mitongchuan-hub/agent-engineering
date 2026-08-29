# c01: Bash 即工具 —— codex 的第一性原理

> codex 源码对照：`tools/handlers/unified_exec`、`exec/` 系列 crate
> 上一步：无（codex_learn 第一课）｜ 下一步：[c02 并行工具](../c02_parallel_tools/)

## 问题

给 Agent 十个专用工具（read_file、write_file、search…），它仍会碰到"工具外"的需求。
但如果你给它一个 **Bash**：读文件、跑测试、git、装依赖、启服务……全都能做。

codex 的原话哲学：**"Bash is all you need"**——通用执行能力 > 一堆专用工具。

## 方案

一个 `execute_bash(command)` 工具 + 安全闸门：

```
模型 --(调用 execute_bash)--> ① 危险预检 --> ② 限时执行 --> ③ 结果回填
```

## 原理（读 code.py）

### ① 危险预检（第一道闸）

```python
DANGEROUS = ["rm -rf /", "mkfs", "dd if=", "shutdown", ":(){ :|:& };:"]
for bad in DANGEROUS:
    if command.strip().startswith(bad):
        return {"status": "blocked", "reason": f"危险命令：{bad}"}
```
注意：这只是**前缀黑名单**——生产中它只是最外层，真正隔离靠 c04 沙箱 + c03 审批。

### ② 限时执行（第二道闸）

```python
proc = subprocess.run(command, shell=True, capture_output=True,
                      text=True, timeout=self.timeout)
```
`timeout` 防死命令；`capture_output` 把 stdout/stderr 抓回来给模型。

### ③ 结果结构化

```python
{"status": "ok", "exit_code": 0, "stdout": "...", "stderr": "..."}
```
**模型看到真实输出才能继续推理**——这是"看得见的 Agent"的基础。

## 运行

```bash
python c01_bash_tool/code.py
# [agent] step 1: bash "python -c ...sqrt(144)"
# [agent] step 1: ok -> ...
# [agent] step 2: bash "echo hello && ls" ...
# 危险预检演示：rm -rf / xxx -> blocked
```

## 面试问答

**Q：为什么 codex 主打 "Bash is all you need"？**
A：专用工具是"设计者想象的边界"，Bash 是"能力的全集"（能跑任意程序、访问任意文件）。给模型万能执行器，它自己能组合出需要的能力。代价是安全风险更大——所以必须配沙箱/审批（c03/c04）。

**Q：工具输出怎么给模型？**
A：结构化 JSON（status/exit_code/stdout/stderr）截断后回填为 tool 消息。模型据此判断"下一步干什么"，错误时还能自查（exit_code≠0 的 stderr 就是诊断信息）。

**Q：shell=True 为什么不安全？**
A：shell 会解析管道/重定向/子 shell，注入面更大。生产做法：用 `execvp` 风格免 shell、参数数组传参、还是进沙箱（c04）。

## 延伸

- c02：多个命令怎么并行跑（两阶段）
- c03：危险命令走审批（人/策略决定）
- c04：真沙箱（降权+隔离+超时）
- 关联 learn-mini-agent：s01 循环 + 本步的 execute_bash = learn-claude-code 里 s01 的真实形态