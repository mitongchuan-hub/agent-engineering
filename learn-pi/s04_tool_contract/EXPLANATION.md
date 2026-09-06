# `code.py` 结构化解读：工具契约与执行流水线

> 代码文件：[`code.py`](./code.py)
>
> 本章重点：模型发出的 `ToolCall` 不是拿到函数后就可以直接执行的命令，而是需要经过查找、参数准备、参数校验、策略检查和中止检查的一条受控流水线。

## 1. 先记住一条执行链

```text
ToolCall
   |
   v
查找工具
   |
   v
prepare_arguments
   |
   v
校验参数
   |
   v
before_tool_call 策略检查
   |
   +-- 找不到/校验失败/被阻止/已 abort
   |       -> 错误 ToolOutcome，不执行工具
   |
   +-- 通过
           -> 执行 tool.execute()
           -> ToolResultMessage
```

代码中最完整的入口是：

```python
outcome = await execute_tool_call(tools, call)
```

它保证：

- 工具不存在时不调用函数。
- 参数不符合 schema 时不调用函数。
- 策略 hook 阻止时不调用函数。
- 已经 abort 时不调用函数。
- 工具函数抛异常时转换为错误结果，而不是击穿外层 Agent Loop。

## 2. 为什么需要“工具契约”

模型返回的工具调用本质上是外部输入：

```python
ToolCall(
    id="call-1",
    name="read_file",
    arguments={"path": "a.txt"},
)
```

不能因为模型给出了工具名和参数，就直接执行：

```python
# 缺少边界控制的做法
tool.execute(call.id, dict(call.arguments))
```

至少需要确认：

1. 这个工具是否存在。
2. 参数结构是否正确。
3. 参数类型是否正确。
4. 是否需要把模型的 shorthand 参数转换成正式形状。
5. 当前策略是否允许这次调用。
6. 当前运行是否已经被中止。

因此，`Tool` 不只是一个函数，而是一份契约：

```python
@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: Schema
    execute: ToolExecutor
    prepare_arguments: Callable[[Any], Any] | None = None
```

## 3. 主要数据结构

### 3.1 `ToolCall`

```python
@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]
```

它表示模型提出的一次调用请求：

- `id`：这次调用的唯一 id。
- `name`：请求使用的工具名。
- `arguments`：模型提供的原始参数。

`arguments` 使用 `Mapping`，表示调用方只需要把它当作映射读取，不要求它一定是可变字典。

### 3.2 `ToolResultMessage`

```python
@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    terminate: bool = False
```

它是工具调用的模型可见结果：

- `tool_call_id` 和原调用对应。
- `tool_name` 表示哪个工具产生结果。
- `content` 是结果文本。
- `is_error=True` 表示调用失败或被拒绝。
- `terminate=True` 表示调用方可以据此终止后续 Agent 流程。

本文件只负责返回 `ToolOutcome`，不会自己处理 `terminate`，也不会直接结束外层 Agent Loop。

### 3.3 `BeforeToolCallResult`

```python
@dataclass(frozen=True, slots=True)
class BeforeToolCallResult:
    block: bool = False
    reason: str | None = None
    terminate: bool = False
```

这是 `before_tool_call` 策略 hook 的决定：

```text
block=False
    允许执行

block=True
    阻止执行

reason
    返回给模型或上层的原因

terminate=True
    同时请求上层终止后续流程
```

### 3.4 `PreparedToolCall`

```python
@dataclass(frozen=True, slots=True)
class PreparedToolCall:
    call: ToolCall
    tool: Tool
    args: dict[str, Any]
```

它表示：

```text
工具已找到
参数已准备
参数已通过校验
可以进入 execute 阶段
```

### 3.5 `ToolOutcome`

```python
@dataclass(frozen=True, slots=True)
class ToolOutcome:
    call: ToolCall
    result: ToolResultMessage
    executed: bool
```

它是对外的统一执行结果：

- `call`：原始调用。
- `result`：成功或失败的消息。
- `executed`：工具函数是否成功执行并返回。

注意：准备阶段失败时也会返回 `ToolOutcome`，但 `executed=False`。

## 4. Schema：工具参数的形状说明

代码用一个简化的 JSON Schema 子集描述参数：

```python
Schema = dict[str, Any]
```

例如 `read_file` 的 schema：

```python
SCHEMA = {
    "type": "object",
    "required": ["path"],
    "properties": {
        "path": {
            "type": "string",
            "minLength": 1,
        },
    },
    "additionalProperties": False,
}
```

它要求：

```text
根值必须是 object
必须有 path
path 必须是非空字符串
不能出现 schema 之外的字段
```

本章验证器支持的主要能力：

| Schema 能力 | 例子 |
|---|---|
| 基本类型 | `object`、`array`、`string`、`boolean` |
| 数字类型 | `integer`、`number` |
| 联合类型 | `"type": ["string", "null"]` |
| 必填字段 | `required` |
| 对象字段 | `properties` |
| 禁止额外字段 | `additionalProperties: False` |
| 数组元素 | `items` |
| 字符串长度 | `minLength` |

它不是完整 JSON Schema，也不是生产级校验库，只实现了本章需要的最小子集。

## 5. `_coerce()`：少量类型转换

```python
def _coerce(value: Any, schema: Schema) -> Any:
```

它尝试处理模型有时把数字或布尔值作为字符串返回的情况：

```text
"42"      -> 42       integer
"3.14"    -> 3.14     number
"true"    -> True     boolean
"false"   -> False    boolean
```

转换失败时保留原值，之后由验证器报告错误：

```text
"not-a-number" 不会强行转换成功
```

这个函数只做非常有限的转换，不是完整的 schema conversion 系统。

## 6. `_matches_type()`：判断基础类型

```python
def _matches_type(value: Any, expected: str) -> bool:
```

它判断 Python 值是否符合 schema 类型。

有一个重要细节：

```python
if expected == "integer":
    return isinstance(value, int) and not isinstance(value, bool)
```

Python 中 `bool` 是 `int` 的子类，所以不能只写 `isinstance(value, int)`，否则 `True` 会被错误地当成整数。

`number` 同样排除 bool：

```python
isinstance(value, (int, float)) and not isinstance(value, bool)
```

## 7. `_validate()`：递归校验参数

```python
def _validate(value: Any, schema: Schema, path: str) -> None:
```

它根据 schema 递归检查参数，并在失败时抛出：

```python
ToolValidationError
```

校验顺序可以概括为：

```text
检查当前值的类型
    |
    v
如果是 object：检查 required、额外字段和 properties
    |
    v
如果是 array：递归检查每个 item
    |
    v
如果是 string：检查 minLength
```

错误路径会被记录下来，例如：

```text
root.path: expected string, got integer
root.edits[0].newText: is required
root.extra: is not allowed
```

带路径的错误比只返回“参数错误”更有用，因为模型或上层可以知道具体哪个字段出了问题。

## 8. `validate_arguments()`：复制后再校验

```python
def validate_arguments(tool: Tool, call: ToolCall) -> dict[str, Any]:
```

它的步骤是：

```text
原始 call.arguments
    |
    v
转成 dict 并 deepcopy
    |
    v
执行有限类型转换
    |
    v
确认根值是 object
    |
    v
递归校验 schema
    |
    v
返回新的 validated args
```

核心代码：

```python
args = deepcopy(dict(call.arguments))
args = _coerce(args, tool.parameters)
_validate(args, tool.parameters, "root")
return args
```

为什么要复制？

```python
raw = {"path": "a.txt"}
call = ToolCall("c1", "read_file", raw)
validated = validate_arguments(tool, call)
validated["path"] = "changed.txt"
```

此时原始参数仍然是：

```python
raw == {"path": "a.txt"}
```

也就是说，校验、转换和后续 hook 不应该偷偷改写模型原始调用。

失败时，函数会包装错误信息：

```text
Validation failed for tool "read_file": root.path: expected string, got integer
Received arguments: {'path': 42}
```

## 9. `prepare_arguments`：先变形，再校验

有些模型会使用 shorthand 形式。例如工具正式要求：

```python
{"edits": [{"oldText": "before", "newText": "after"}]}
```

但模型可能输出：

```python
{"oldText": "before", "newText": "after"}
```

这时可以在 `Tool` 上提供：

```python
prepare_arguments=lambda args: {
    "edits": args.get("edits", [])
    + ([
        {
            "oldText": args["oldText"],
            "newText": args["newText"],
        }
    ] if "oldText" in args else [])
}
```

执行顺序是：

```text
模型 shorthand
    -> prepare_arguments()
    -> 正式参数形状
    -> validate_arguments()
```

所以 prepare 的结果必须满足 schema。代码特意规定：

> `prepare_arguments` 在校验之前执行。

如果 prepare 函数本身抛异常，也会被捕获为错误 `ToolOutcome`，工具不会执行。

## 10. `prepare_tool_call()`：执行前的全部决策

```python
async def prepare_tool_call(...):
    ...
```

它只做准备，不调用真正的工具函数。

返回值有两种：

```text
PreparedToolCall
    所有检查通过，可以执行

ToolOutcome
    准备阶段失败，已经有错误结果，不执行
```

完整流程：

### 第一步：按名字查找工具

```python
tool = next(
    (candidate for candidate in tools if candidate.name == call.name),
    None,
)
```

找不到时立即返回：

```text
Tool xxx not found
```

这时不会进入 prepare、validate 或 execute 阶段。

### 第二步：准备参数

```python
raw_arguments = dict(call.arguments)
if tool.prepare_arguments is not None:
    raw_arguments = tool.prepare_arguments(raw_arguments)
```

它允许把模型输出的 shorthand 转换成工具正式需要的形状。

### 第三步：校验参数

```python
prepared_call = ToolCall(call.id, call.name, raw_arguments)
validated = validate_arguments(tool, prepared_call)
```

校验成功后，`validated` 是一份独立的参数字典。

### 第四步：执行前 hook

```python
decision = before_tool_call(call, validated)
```

hook 可以：

- 记录调用。
- 检查权限。
- 检查用户确认状态。
- 修改已经校验的参数。
- 返回 `BeforeToolCallResult(block=True)` 阻止执行。

如果 hook 是异步函数，代码会等待它：

```python
if inspect.isawaitable(decision):
    decision = await decision
```

### 第五步：再次检查 abort

```python
if signal is not None and signal.aborted:
    return _error(call, "Operation aborted")
```

代码在 hook 之后检查 abort，避免在策略等待期间发生中止后仍执行工具。

### 第六步：返回 PreparedToolCall

```python
return PreparedToolCall(call, tool, validated)
```

到这里仍然没有调用 `tool.execute`，只是说明它已经可以安全进入执行阶段。

## 11. 一个重要且容易忽略的 hook 语义

本实现允许 hook 修改已经校验过的参数：

```python
def before(_call, args):
    args["path"] = 123
    return None
```

之后执行阶段会直接使用修改后的值：

```python
prepared.tool.execute(prepared.call.id, prepared.args)
```

不会再次校验。

因此即使原始值符合 schema：

```python
{"path": "a.txt"}
```

hook 改成：

```python
{"path": 123}
```

工具仍会收到 `123`。

这是本章模拟的 Pi 上游契约，测试特意固定了这个行为。它意味着：

```text
schema 校验保护的是 hook 之前的参数
hook 修改后的参数由 hook 自己负责正确性
```

从安全和业务角度看，实际 hook 应谨慎修改参数；如果业务要求修改后仍满足 schema，就需要额外重新校验。

## 12. `execute_tool_call()`：真正执行工具

```python
async def execute_tool_call(...) -> ToolOutcome:
```

它先调用：

```python
prepared = await prepare_tool_call(...)
```

如果准备阶段已经返回错误结果：

```python
if isinstance(prepared, ToolOutcome):
    return prepared
```

直接返回，不执行工具。

准备成功后才执行：

```python
value = prepared.tool.execute(
    prepared.call.id,
    prepared.args,
)
```

工具既可以是同步函数，也可以是异步函数：

```python
if inspect.isawaitable(value):
    value = await value
```

成功时返回：

```python
ToolOutcome(
    call,
    ToolResultMessage(call.id, call.name, str(value)),
    executed=True,
)
```

工具函数抛异常时：

```python
except Exception as error:
    return _error(call, str(error))
```

结果会变成：

```text
is_error=True
executed=False
```

这样异常可以作为 `ToolResultMessage` 回到模型，而不会直接打断外层 Agent Loop。

## 13. `_error()`：统一构造失败结果

```python
def _error(
    call: ToolCall,
    message: str,
    *,
    terminate: bool = False,
) -> ToolOutcome:
```

它把各种失败统一成：

```python
ToolOutcome(
    call=call,
    result=ToolResultMessage(
        tool_call_id=call.id,
        tool_name=call.name,
        content=message,
        is_error=True,
        terminate=terminate,
    ),
    executed=False,
)
```

可能进入 `_error()` 的场景包括：

- 工具不存在。
- prepare 参数失败。
- schema 校验失败。
- before hook 阻止。
- signal 已 abort。
- 工具执行函数抛异常。

统一结果形状的好处是，上层只需要处理一种返回类型，而不需要为每个异常分支写一套逻辑。

## 14. demo 逐步解释

### 14.1 定义 `edit` 工具

`edit` 工具正式要求：

```python
{
    "edits": [
        {
            "oldText": "...",
            "newText": "...",
        }
    ]
}
```

它的 `execute` 函数只返回修改了多少项：

```python
execute=lambda _id, args: f"edited {len(args['edits'])} item(s)"
```

### 14.2 模型给出 shorthand

```python
call = ToolCall(
    "call-1",
    "edit",
    {"oldText": "before", "newText": "after"},
)
```

这个参数没有 `edits` 字段，直接校验会失败。

### 14.3 prepare 把它转换成正式形状

转换后相当于：

```python
{
    "edits": [
        {
            "oldText": "before",
            "newText": "after",
        }
    ]
}
```

校验通过，工具执行，输出：

```text
executed: True
result: edited 1 item(s)
```

### 14.4 策略 hook 阻止调用

之后使用：

```python
before_tool_call=lambda _call, _args: BeforeToolCallResult(
    block=True,
    reason="policy denied",
)
```

此时输出：

```text
blocked: policy denied (executed=False)
```

注意：这里 `edit` 的 `execute` 根本没有被调用。

## 15. 各种失败行为对照

| 情况 | 是否执行工具 | 返回结果 |
|---|---:|---|
| 工具存在、参数合法、hook 放行 | 是 | `is_error=False` |
| 工具不存在 | 否 | `Tool ... not found` |
| 参数类型错误 | 否 | `ToolValidationError` 文本 |
| 缺少 required 字段 | 否 | `is_error=True` |
| prepare 函数抛异常 | 否 | 错误 `ToolOutcome` |
| hook 返回 `block=True` | 否 | hook 的 `reason` |
| hook 后 signal 已 abort | 否 | `Operation aborted` |
| 工具函数抛异常 | 已进入执行但结果失败 | `is_error=True` |

所有失败都尽量返回结构化的 `ToolOutcome`，而不是直接抛出到最外层。

## 16. 与第 01 章的区别

第 01 章的工具执行相对直接：

```text
找到工具
    -> 调用 execute
    -> 捕获异常
    -> ToolResultMessage
```

第 04 章增加了完整的执行前边界：

```text
找到工具
    -> prepare
    -> validate
    -> before hook
    -> abort 检查
    -> execute
    -> ToolResultMessage
```

这说明：

> Tool Call 只是模型的意图，Prepared Tool Call 才是通过准备和校验、可以交给执行器的调用。

## 17. 与第 05 章的关系

本章只关注**单个工具调用的契约和执行准备**。

如果一条 assistant 消息包含多个 tool call，第 05 章还要解决：

- 工具是否并行执行。
- 某些工具是否必须串行。
- 工具完成事件的顺序。
- transcript 中工具结果的顺序。

本章的 `execute_tool_call()` 是单调用粒度的基础组件。

## 18. 建议的阅读顺序

重新阅读源码时建议按以下顺序：

1. 先看 `demo()`，理解 shorthand 参数和策略阻止。
2. 看 `Tool`、`ToolCall`、`ToolOutcome`，明确对象边界。
3. 看 `execute_tool_call()`，掌握主入口。
4. 进入 `prepare_tool_call()`，按查找、prepare、validate、hook、abort 的顺序阅读。
5. 看 `validate_arguments()`、`_validate()` 和 `_matches_type()`，理解 schema 校验。
6. 最后看 `_error()` 和异常捕获，理解失败如何变成模型可见结果。

最值得记住的三条规则是：

```text
先准备和校验，再执行。
```

```text
准备阶段失败，返回错误结果，不调用工具。
```

```text
工具异常也转换为 ToolResult，不直接击穿 Agent Loop。
```

## 总结

第 04 章把工具调用从一个裸函数调用升级成一条有边界的流水线：

```text
模型意图
  -> 参数变形
  -> 参数校验
  -> 策略决策
  -> abort 检查
  -> 工具执行
  -> 统一结果
```

一句话记忆：

> `ToolCall` 是模型提出的请求，`PreparedToolCall` 是通过执行前检查后的请求，`ToolOutcome` 是最终交给上层和模型的统一结果。

验证命令：

```powershell
E:\anaconda\Scripts\conda.exe run -n agent-engineering python learn-pi/s04_tool_contract/code.py
E:\anaconda\Scripts\conda.exe run -n agent-engineering python -m pytest learn-pi/tests/test_s04_tool_contract.py
```
