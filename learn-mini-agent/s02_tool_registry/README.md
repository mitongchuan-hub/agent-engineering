# s02: Tool Registry —— 函数签名就是 Schema

> **Harness 层**：工具注册是 Agent 能力的第一入口。
> 前一步：[s01 Agent Loop](../s01_agent_loop/) ｜ 后一步：[s03 LLM 客户端](../s03_llm_client/)

## 问题

s01 里每个工具定义都是**手写 JSON**：

```python
TOOLS = [{"type": "function", "function": {"name": "add",
    "description": "两个整数相加",
    "parameters": {"properties": {"a": {"type": "integer"}, ...}}}}]
```

工具多了以后必然出问题：
- 代码改了签名，说明书忘了改 → 模型按旧 Schema 传参 → 执行报错
- 手写容易漏 `required` / 写错类型
- 加一个工具 = 心累地复制粘贴

## 解决方案

**让 Python 的函数签名自己生成 Schema**。利用两个标准库：

| 工具 | 作用 |
|---|---|
| `inspect.signature(func)` | 拿参数名、默认值、是否必填 |
| `typing.get_type_hints(func)` | 拿真实的类型注解（含字符串注解解析） |

```python
@registry.tool(arg_desc={"a": "第一个整数"})
def add(a: int, b: int) -> int:
    """两个整数相加"""
    return a + b
```
自动产出：
```json
{"type":"function","function":{"name":"add","description":"两个整数相加",
 "parameters":{"type":"object","properties":{"a":{"type":"integer"}},
 "required":["a"]}}}
```

## 工作原理

### ① 类型映射（递归）

```python
_SCALAR = {str: "string", int: "integer", float: "number", bool: "boolean"}

def _to_schema_type(t):
    if origin is typing.Union:      # Optional[int] -> 可空
        ...
    if origin is list:              # list[str] -> array(items)
        ...
    if t in _SCALAR:
        return {"type": _SCALAR[t]} # int -> "integer"
    return {"type": "string"}       # 未知类型兜底
```

### ② 必填 vs 可选

```python
if p.default is not inspect.Parameter.empty:
    # 有默认值的参数 -> 不进 required，附带 default 提示模型
else:
    required.append(pname)
```

### ③ 一个经典坑（自测送分题）

```python
# 文件顶部若写了 from __future__ import annotations，
# 注解会变成字符串 'int' 而非 int 类型！
# inspect.signature 默认不解析，必须用 get_type_hints 取真实类型：
anno = hints.get(pname, p.annotation)
```
我们实际开发时就被这个坑坑过——单测 `test_types_and_required` 抓到 `years: int` 被生成为 `"string"`。**写测试的价值就在这**（s06 展开）。

### ④ 执行与异常兜底

```python
def call(self, name, arguments):
    args = json.loads(arguments)               # 模型给的参数是 JSON 字符串
    if not isinstance(args, dict):
        return "错误：参数必须是 JSON 对象 ..."   # 返回字符串，不让 Agent 崩
    ...
    except TypeError as e:
        return f"工具调用参数错误：{e}。请参考工具 schema 修正后重试。"
```
**原则：工具错误 = 回传模型让它自愈，而不是抛异常炸掉整个循环。**

## 运行

```bash
python s02_tool_registry/code.py
# 输出：自动生成的两个 schema + 演示模型调用 add + 参数错误兜底演示
```

## 练习

1. 给 `multiply` 加一个可选参数 `round_result: bool = False`，看 schema 怎么变
2. 写一个返回 `list[str]` 的工具，确认生成 `"type": "array"`
3. 把 `arg_desc` 去掉，观察 description 从哪里来（答案：函数 docstring）

## 自测问答

**Q：Function Calling 的协议长什么样？**
A：模型侧接收 `tools: [{type:"function", function:{name, description, parameters(JSON Schema)}}]`；响应侧返回 `tool_calls: [{id, function:{name, arguments(string)}}]`。参数是字符串，由宿主 `json.loads` 后执行。

**Q：为什么要用函数签名生成 Schema，而不是手写？**
A：单一事实来源，避免"代码与说明书漂移"；新增工具成本趋近于零；类型错误在开发期暴露而不是运行期。

**Q：工具调用的参数会出什么问题？**
A：三种典型：不是合法 JSON、类型不匹配、缺必填字段。工程上统一兜底：捕获 TypeError/Exception → 返回错误字符串 → 模型自愈重试（s09 展开）。

## 延伸阅读

- s09：参数类型兜底（真实 Bug 案例：模型把 arguments 传成 JSON 字符串）
- s06：我们为 schema 生成写了单测，也正是单测抓到了上面的注解坑
- 参考实现：`openai/codex` 的 `tools/registry.rs`（31KB，功能相同，Rust 版）