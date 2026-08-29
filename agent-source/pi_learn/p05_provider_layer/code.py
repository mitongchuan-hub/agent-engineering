#!/usr/bin/env python3
"""
p05_provider_layer.py - pi_learn 第 5 步：provider 层（模型无关）

pi 的 packages/ai/src/providers/ 里有 40+ 家模型，每家一个文件：
    openai.ts / anthropic.ts / deepseek.ts / qwen.ts / kimi-coding.ts ...
每个 provider 暴露统一接口（chat/stream），Agent 只认接口不认厂商。

本步重建：
    ① Provider 基类（统一 chat 接口）
    ② OpenAIProvider / DeepSeekProvider / FakeProvider 三家实现
    ③ ProviderRegistry：按名字取 provider，切换零侵入

面试点：模型无关的三层——接口层（Provider 基类）/ 实现层（各家）/
配置层（.env 里选）。业务代码写完不再改。

Usage:
    python p05_provider_layer/code.py
"""


# ---------------------------------------------------------------- 接口层

class Provider:
    """统一模型接口（对应 pi providers 的约定）。"""

    name = "base"

    def chat(self, messages: list, tools=None) -> dict:
        """返回标准 assistant 消息（content + tool_calls）。子类实现。"""
        raise NotImplementedError

    def __repr__(self):
        return f"<Provider {self.name}>"


# ---------------------------------------------------------------- 实现层

class OpenAIConvention(Provider):
    """OpenAI 风格：base_url 指向 OpenAI 兼容端点。"""

    name = "openai"

    def __init__(self, base_url: str = "https://api.openai.com/v1"):
        self.base_url = base_url

    def chat(self, messages, tools=None):
        return _sdk_call(self.base_url, messages, tools)  # 教学版：见下方桩


class DeepSeekProvider(Provider):
    """DeepSeek：同协议，不同 base_url/model。"""

    name = "deepseek"

    def __init__(self, base_url: str = "https://api.deepseek.com/v1"):
        self.base_url = base_url

    def chat(self, messages, tools=None):
        return _sdk_call(self.base_url, messages, tools)


class FakeProvider(Provider):
    """本地假模型：无 key 也能演示"选 provider"的机制。"""

    name = "fake"

    def chat(self, messages, tools=None):
        return {"role": "assistant",
                "content": f"（fake 回复) 收到 {len(messages)} 条消息",
                "tool_calls": None}


def _sdk_call(base_url: str, messages, tools) -> dict:
    """真实 SDK 调用桩（教学版示意；配 key 时换真实现）。"""
    return {"role": "assistant",
            "content": f"（{base_url.split('//')[1] or base_url} 调用示意）",
            "tool_calls": None}


# ---------------------------------------------------------------- 注册层

class ProviderRegistry:
    """按名字取 provider：加新厂商 = 注册一个类，零侵入。"""

    def __init__(self):
        self._providers = {}

    def register(self, provider: Provider) -> "ProviderRegistry":
        self._providers[provider.name] = provider
        return self

    def get(self, name: str) -> Provider:
        if name not in self._providers:
            raise KeyError(f"未知 provider: {name}，可用: {sorted(self._providers)}")
        return self._providers[name]


if __name__ == "__main__":
    import os
    from pathlib import Path

    # 读 .env 决定用哪家（密钥统一放仓库根 .env，向上回溯查找）
    here = Path(__file__).resolve()
    target = None
    for base in [here.parent, here.parent.parent, here.parent.parent.parent,
                 here.parent.parent.parent.parent]:
        if (base / ".env").is_file():
            target = base / ".env"
            break
    model_choice = "fake"
    if target:
        for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("LLM_BASE_URL="):
                u = line.split("=", 1)[1].strip()
                model_choice = "deepseek" if "deepseek" in u else "openai"

    registry = (ProviderRegistry()
                .register(FakeProvider())
                .register(OpenAIConvention())
                .register(DeepSeekProvider()))

    print(f"演示：provider 层（当前从 .env 解析到：{model_choice}）\n")
    for name in ["fake", "openai", "deepseek", "openai"]:
        prov = registry.get(name)
        print(f"  用 {prov} 调用：{prov.chat([{'role': 'user', 'content': 'hi'}])['content']}")

    try:
        registry.get("qwen")
    except KeyError as e:
        print(f"\n  未注册的厂商会被明确拒绝：{e}")

    print("""
[结论] provider 层的三个收益：
       1. 业务代码只见 Provider 接口，新增厂商=注册实现，零侵入
       2. 每家实现单独治理（鉴权、重试、限流各管各的）
       3. pi 有 40+ 家、甚至带 OAuth（登录 GitHub Copilot / OpenAI Codex 也能当 provider）
       本步的 registry.get 是 selector，生产还会加"模型不可用自动切换"（重试/降级）""")