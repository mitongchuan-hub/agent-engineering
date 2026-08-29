#!/usr/bin/env python3
"""
s10_comprehensive.py - 综合：把十步拼成一个完整应用

    s01 循环 + s02 注册 + s03 客户端 + s04 上下文
  + s05 打分器 + s06 评测 + s07 MCP + s08 桥接 + s09 健壮性
  = 简历 × JD 匹配 Agent（完整闭环）

本步演示真实数据流（无需 Key）：
    list_files → read_text_file(简历) → read_text_file(JD×2)
    → compute_match(×2) → write_file(报告) → 总结

配 Key 时（.env 填入 LLM_API_KEY），改为真实 LLM 驱动同一个 Agent 循环
完成以上全部步骤（与 resume-matcher 完整版行为一致）。

Usage:
    python s10_comprehensive/code.py          # 演示（无需 Key）
    LLM_API_KEY=sk-xxx python s10_comprehensive/code.py   # 真实 LLM 驱动
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------- 加载 .env（若存在）

def load_env() -> None:
    """加载 learn-mini-agent/.env（否则真实模式读不到 Key）。"""
    p = PROJ / ".env"
    if p.is_file():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k:
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

# 复用前面几步的组件（综合 = 拼装）
from s02_tool_registry.code import ToolRegistry  # noqa: E402
from s05_resume_matcher.code import compute_match  # noqa: E402

DATA = ROOT / "data"


# ---------------------------------------------------------------- ① 注册 4 个领域工具

def build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.tool(description="列出目录下的文件", arg_desc={"directory": "目录路径"})
    def list_files(directory: str):
        return {"files": sorted(p.name for p in Path(directory).iterdir())}

    @registry.tool(description="读取文本文件内容", arg_desc={"path": "文件路径"})
    def read_text_file(path: str):
        return {"content": Path(path).read_text(encoding="utf-8")}

    @registry.tool(description="简历×JD 匹配打分（技能/年限/学历/总分/结论）",
                   arg_desc={"resume_text": "简历全文", "jd_text": "JD 全文"})
    def match(resume_text: str, jd_text: str):
        return compute_match(resume_text, jd_text)

    @registry.tool(description="写入文件（保存报告）", arg_desc={"path": "路径", "content": "内容"})
    def write_file(path: str, content: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")
        return {"ok": True, "chars": len(content)}

    return registry


# ---------------------------------------------------------------- ② 确定性演示管线

def run_pipeline() -> str:
    """无 Key 时的确定性演示：和真实 Agent 同一套工具，同一套顺序（脚本驱动）。"""
    registry = build_registry()
    resume = str(DATA / "resume.md")
    jd1, jd2 = str(DATA / "jd_ai.md"), str(DATA / "jd_backend.md")
    report = str(ROOT / "report.md")

    print("② 真实数据流（确定性演示管线）")
    print("[1] list_files :", registry.call("list_files", json.dumps({"directory": str(DATA)}))[:120])
    rt = json.loads(registry.call("read_text_file", json.dumps({"path": resume})))
    resume_text = rt["content"] if isinstance(rt, dict) else str(rt)
    print(f"[2] read resume : 读取 {len(resume_text)} 字符")

    lines = ["# 简历 × JD 匹配报告（s10 综合演示）\n"]
    total = 0
    for name, path in [("ai_engineer", jd1), ("backend_engineer", jd2)]:
        jd_text = json.loads(registry.call("read_text_file", json.dumps({"path": path})))["content"]
        r = json.loads(registry.call("match", json.dumps(
            {"resume_text": resume_text, "jd_text": jd_text})))
        total += 1
        lines.append(f"\n## {name}\n- 总分：**{r['overall_score']}**（{r['verdict']}）"
                     f"- 缺口：{', '.join(r['gap_skills']) or '无'}")
        print(f"[3] match {name} : {r['overall_score']} 分，缺口 {r['gap_skills'] or '无'}")

    summary = f"\n共评估 {total} 个岗位。最匹配岗见完整报告。"
    lines.append(summary)
    ok = json.loads(registry.call("write_file",
                                  json.dumps({"path": report, "content": "\n".join(lines)})))
    print(f"[4] write_file : 报告已保存 {report}（{ok['chars']} 字符）")
    print(f"[5] 总结：{summary}\n")
    return report


# ---------------------------------------------------------------- ③ 真实 LLM 驱动（配 Key 时）

def run_real() -> None:
    """真实 LLM 驱动同一个循环：模型自己决定调哪些工具。"""
    from s03_llm_client.code import ChatClient

    registry = build_registry()
    chat = ChatClient(base_url=os.getenv("LLM_BASE_URL", ""),
                      api_key=os.getenv("LLM_API_KEY", ""),
                      model=os.getenv("LLM_MODEL", ""))
    messages = [{"role": "user", "content": f"评估 {DATA} 下的简历与 JD，"
                                            f"生成报告保存到 {ROOT}/report.md"}]
    for step in range(1, 10):
        resp = chat.chat(messages, tools=registry.schemas())
        messages.append(resp)
        if not resp.get("tool_calls"):
            print("最终回答：", (resp.get("content") or "")[:300])
            return
        for tc in resp["tool_calls"]:
            name = tc["function"]["name"]
            print(f"[agent] step {step}: {name}")
            out = registry.call(name, tc["function"]["arguments"])
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out[:1500]})
    print("(达到迭代上限)")


if __name__ == "__main__":
    key = os.getenv("LLM_API_KEY", "")
    if key and not key.startswith("sk-your"):
        print("① 真实 LLM 模式")
        run_real()
    else:
        report = run_pipeline()
        print(f"[ok] 完整流程结束，报告：{report}")
        print("    （配 Key 后同一套工具交给真实 LLM 自主决策，行为与完整版一致）")
    sys.exit(0)