# x06: 综合 —— 迷你插件引擎（提示词即软件的完整链路）

> 前五步合体：manifest(x01) → allowed-tools(x02) → 剧本(x03) → hooks(x04) → 命令(x05)
> 上一步：[x05 命令解析器](../x05_commands/) ｜ 完（claude_learn 收官）

## 一张图看懂 claude 插件体系（读 code.py 主流程）

```
用户输入 /review
   │
   ▼
① 加载（manifest + commands）      ← x01/x05
② 授权（authz：allowed-tools）     ← x02   deny by default
   │  未授权 → 拒绝（审计记一条）
   ▼
③ 拦截（hooks：危险命令/改写）      ← x04
   │  拒绝 → 拦下（审计记一条）
   ▼
④ 执行（剧本调度）                 ← x03（简化为逐条模拟）
   │
   ▼
审计日志（每步 authz / hook 可查）  ← 可观测
```

## 运行

```bash
python x06_comprehensive/code.py
# ✅ Bash(gh pr view 42)        authz=True hook=allow
# 🚫 Bash(cat /etc/passwd)      不在白名单 → 拒绝
# ✅ mcp__report__writemarkdown authz=True
# 审计日志全量输出
```

## 四层职责分离（自测问答的答案）

| 层 | 负责 | 对应前面 |
|---|---|---|
| 加载 | 能力从哪来 | x01/x05 |
| 授权 | 能不能用（静态） | x02 |
| 拦截 | 这次该不该/怎么用（动态） | x04 |
| 执行 | 到底怎么跑 | x03 |

**"提示词即软件"= 软件工程四件套换了个实现介质**：
接口规格（YAML 头）、权限（allowed-tools）、钩子（hooks）、逻辑（剧本）。

## 收官

至此 **claude 系列完成**，四家教学全家福：

| 教学库 | 主题 | 步数 |
|---|---|---|
| learn-mini-agent | 手写框架 | s01~s10 |
| codex_learn | 工程外壳 | c01~c07 |
| deepseek_learn | 可插拔架构 | d01~d07 |
| pi_learn | 事件驱动 | p01~p07 |
| **claude_learn** | **提示词生态** | **x01~x06** |

回总览 [agent-source/README.md](../../README.md) 看四家对比与速查。