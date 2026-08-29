# p05: Provider 层 —— 模型无关的工程答案

> pi 源码对照：`ai/src/providers/`（40+ 家，每家一文件 + .models.ts 生成清单）
> 上一步：[p04 失败进流](../p04_failure_in_stream/) ｜ 下一步：[p06 分支压缩](../p06_branch_compaction/)

## 问题

业务代码直接调 openai SDK？换 DeepSeek 就得改代码。
**模型无关 = 接口 + 实现 + 配置 三层隔离。**

## 方案

```
业务代码 ──▶ Provider 接口（chat/stream）◀─ 实现：
                                         OpenAI / DeepSeek / Fake / Qwen ...
                    ▲
              ProviderRegistry.get(name)  ← .env 里选哪家
```

## 原理（读 code.py）

```python
class Provider:
    def chat(self, messages, tools=None): raise NotImplementedError

class OpenAIConvention(Provider):    # 同协议不同端点
    def __init__(self, base_url="https://api.openai.com/v1"): ...

class DeepSeekProvider(Provider):    # 加一家 = 加一个类
    ...

registry = (ProviderRegistry()
            .register(FakeProvider())
            .register(OpenAIConvention())
            .register(DeepSeekProvider()))
prov = registry.get(choice)          # 运行时切换，代码零改动
```

## 运行

```bash
python p05_provider_layer/code.py
# 用 <Provider fake> 调用：...
# 用 <Provider openai> 调用：...
# 未注册的厂商会被明确拒绝：未知 provider: qwen
```

## 自测问答

**Q：为什么 OpenAI 兼容协议成了事实标准？**
A：DeepSeek/智谱/Moonshot/Qwen 全部兼容 OpenAI 格式——协议统一让"注册新厂商"成本趋近于零；pi 甚至把 GitHub Copilot、OpenAI Codex 的 OAuth 登录也包成 provider。

**Q：provider 层还要管什么？**
A：每家单独的鉴权、重试、限流、模型清单（pi 的 .models.ts 是生成的文件）、OAuth。接口只管 chat，治理各管各的。

**Q：选择策略呢？**
A：注册表只是 get；生产还加 failover（主模型挂了切备用）、按任务选模型（重活贵模型/轻活便宜模型）。

## 延伸

- learn-mini-agent s03：我们的 ChatClient 是"单家适配"；这里升级为"多 provider 注册"
- p04：流的失败处理 + provider 层 = 完整模型接入方案