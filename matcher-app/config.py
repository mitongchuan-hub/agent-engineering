"""全局配置：改这里或设置环境变量即可切换任意 OpenAI 兼容的 API。

常用服务（都是 OpenAI 兼容协议，只换 base_url + model）：
    OpenAI        https://api.openai.com/v1              gpt-4o-mini
    DeepSeek      https://api.deepseek.com/v1            deepseek-chat   (便宜，国内直连)
    智谱 GLM      https://open.bigmodel.cn/api/paas/v4   glm-4-flash
    Moonshot      https://api.moonshot.cn/v1             moonshot-v1-8k
    Qwen 通义     https://dashscope.aliyuncs.com/compatible-mode/v1
"""
import os


def _load_dotenv() -> None:
    """极简 .env 加载器（不加依赖）：向上回溯找到第一份 .env，逐行注入 os.environ
    （密钥统一放仓库根 .env，不覆盖已有环境变量）。"""
    import os
    import sys
    from pathlib import Path
    candidates = [Path.cwd()] + list(Path(__file__).resolve().parents)
    for base in candidates:
        path = base / ".env"
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            raw = f.read()
        text = None
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                os.environ.setdefault(k, v)
        return


_load_dotenv()  # 允许从项目根目录 .env 读取配置（已被 .gitignore 排除）

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-在这里粘贴你的key")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

# 上下文预算（字符）：演示 MessageBuffer 的窗口截断
CONTEXT_CHAR_BUDGET = 24000
TEMPERATURE = 0.3
MAX_AGENT_ITERS = 12

# 没配 key 时自动进入 Mock 模式：走确定性规则管线，不调用 LLM，方便先跑通
MOCK_MODE = (not LLM_API_KEY) or LLM_API_KEY.startswith("sk-在这里") or "sk-xxxx" in LLM_API_KEY

# 透传给 LLM 的附加请求参数（如推理模型的 effort 控制），.env 里可配 LLM_REASONING_EFFORT=xhigh
EXTRA_LLM_PARAMS = {}
REASONING = os.environ.get("LLM_REASONING_EFFORT")
if REASONING:
    EXTRA_LLM_PARAMS["reasoning_effort"] = REASONING