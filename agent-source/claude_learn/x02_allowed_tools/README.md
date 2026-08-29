# x02: allowed-tools —— 声明式权限白名单

> claude 源码对照：`plugins/*/commands/*.md` 的 YAML 头（真实样例见 code-review.md）
> 上一步：[x01 插件结构](../x01_plugin_manifest/) ｜ 下一步：[x03 多 Agent 剧本](../x03_playbook/)

## 问题

模型有了工具，凭什么用哪个？claude-code 的答案在**命令头部**：
不是运行时审批，而是**声明式边界**——预先锁死。

## 方案（真实格式）

```yaml
allowed-tools: Bash(gh issue view:*), Bash(gh pr view:*),
               mcp__github_inline_comment__create_inline_comment
```
- `Bash(gh pr view:*)`：允许 bash，且命令以 `gh pr view` 开头（`:*` = 任意后缀）
- `mcp__server__tool`：允许调用 MCP 服务器上某个精确工具
- 白名单之外 = 一律拒绝（**deny by default**）

## 原理（读 code.py）

```python
@dataclass
class BashRule:
    arg_prefix: str      # "gh pr view"
    def matches(self, cmd): return cmd.startswith(self.arg_prefix)

def check(policy, kind, value):
    # bash: 前缀匹配；mcp: 精确匹配；其余：拒绝
    return ok, hit
```

## 运行

```bash
python x02_allowed_tools/code.py
# ✅ [bash] gh pr view 123      -> 命中前缀
# 🚫 [bash] rm -rf /            -> 不在白名单
# ✅ [mcp ] github_inline_comment/create_inline_comment -> 精确命中
# 🚫 [mcp ] .../delete_comment  -> 非白名单工具
```

## 自测问答

**Q：allowed-tools 和 codex approvals 的区别？**
A：approvals 是**决策时**审批（执行瞬间人/策略决定）；allowed-tools 是**执行前**锁死（命令级白名单）。前者活、后者严——claude 用声明式边界，因为它的命令是可审计的固定剧本。

**Q：`:*` 通配会不会太宽松？**
A：在可控范围：`gh pr view 123` 只会查 PR，危害面小。通配的边界 = 你对该工具子命令的信任度；高危子命令不开通配。

## 延伸

- x04：白名单之外的"过程式"防线——hooks
- x06：引擎里 authz 层即此实现
- 对照 codex_learn c03（审批流）理解两种权限模型