# d04: 严格 Schema —— 参数的守门员

> deepseek 源码对照：`packages/core/tools/`（schema/json-schema/ptc/py-types/ts-types）
> 上一步：[d03 Inbox](../d03_inbox/) ｜ 下一步：[d05 子 Agent](../d05_subagent/)

## 问题

模型生成的工具参数**不一定合法**：类型错（`"recipient": 12345`）、缺字段、枚举值乱填。
如果直接 `func(**args)`，函数内部一堆防御代码；更糟的是，非法参数**进了日志和状态**。

## 方案：schema = 合同 + 守门员

```
模型要调 send_notification(channel=email, recipient=12345)
        │
        ▼
   ① schema 校验器 ──✗──▶ 拒绝执行，返回原因（不进函数！）
        │ ✓
        ▼
   ② 执行函数（永远收到合法输入）
```

## 原理（读 code.py）

### ① 签名 → schema（复用 learn-mini-agent s02）

```python
def strict_schema(name, description, arg_desc=None):
    def deco(func):
        # inspect + type hints 自动生成 schema & 必填列表
        func._schema = {...}
```

### ② 运行时校验（守门员）

```python
def validate(schema, args):
    for req in required:
        if req not in args: return False, f"缺少必填参数 {req!r}"
    for k, v in args.items():
        if t == "integer" and not isinstance(v, int):
            return False, f"参数 {k!r} 应为 integer"
        ...
    return True, ""
```

### ③ 错误 ≠ 崩溃，回传模型自愈

```python
def invoke(func, raw_args):
    ok, reason = validate(func._schema, args)
    if not ok:
        return f"拒绝：{reason}（schema 守门员拦截）"   # 模型看到原因可以改
```
和 learn-mini-agent s09 的错误回传一脉相承——**守门员拦下≠任务失败，是信息**。

## 运行

```bash
python d04_strict_schema/code.py
# 合法参数 -> 放行；类型错/缺必填/数组写成字符串 -> 拒绝（带原因）
```

## 自测问答

**Q：schema 只给模型看吗？**
A：不够。生产里它有三重身份：① 提示模型怎么传参（协议）；② 校验模型传的参数（守门）；③ 记录审计（谁传了什么）。deepseek 把②做成独立工具链，还支持 Python/TS 多语言类型推导。

**Q：拒绝后模型能自愈吗？**
A：能。错误原因以 tool 消息回传 → 模型参照原因修正参数重试（s09 的自愈循环）。关键是把原因写得"可执行"（告诉它要 integer，不是要它猜）。

**Q：校验开销大吗？**
A：小。纯内存比较，比起模型调用可忽略。所以**校验永远放在执行前**，不做白不做。

## 延伸

- d06：参数校验之外，输出也可能超长——裁剪是输出侧的另一道闸
- 对比 codex c03 审批：schema 守门员管"参数对不对"，审批管"该不该做"