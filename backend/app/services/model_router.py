"""大模型抽象层。

走 OpenAI 兼容端点（地址由 config.py / .env 配置），
模型 glm-5.2 同时处理视觉识别和文本生成（讲解/对话）。
所有外部 LLM 调用集中在此文件，业务代码只调 ModelRouter 的方法。
换模型/换端点只改 config.py + 此文件。
"""

import json
from typing import Any

from openai import AsyncOpenAI

from app.config import settings


def _extract_json(text: str) -> dict | None:
    """从 LLM 输出中提取 JSON 对象。

    用栈匹配法正确处理嵌套花括号和字符串内的花括号/引号。
    支持 ```json 包裹、裸 JSON、前后有说明文字。
    """
    if not text:
        return None

    # 1. 先尝试直接解析（最干净的情况）
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 2. 找第一个 '{'，用栈匹配找到对应的 '}'
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # 找到完整的 JSON 对象
                try:
                    result = json.loads(text[start : i + 1])
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    pass
                # 继续找下一个 '{'
                next_start = text.find("{", i + 1)
                if next_start == -1:
                    return None
                # 递归处理剩余文本（避免深递归，改用循环）
                return _extract_json(text[next_start:])
    return None


class ModelRouter:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=60)

    # === 展物识别（视觉）===

    async def recognize(
        self, image_base64: str, museum_id: int, hint: str | None = None
    ) -> dict[str, Any]:
        """调 glm-5.2 视觉能力识别展物，返回候选 + 置信度。"""
        return await self._call_vision_llm(image_base64, museum_id, hint)

    async def _call_vision_llm(
        self, image_base64: str, museum_id: int, hint: str | None
    ) -> dict[str, Any]:
        prompt = (
            "你是博物馆文物识别专家。识别这张照片里的展品，返回 JSON：\n"
            '{"name":"展品名","category":"类别","dynasty":"朝代","confidence":0.0-1.0}\n'
            f"上下文：博物馆ID {museum_id}，类型提示：{hint or '未知'}。\n"
            "confidence 反映你的把握，0.85 以上才算高置信。只返回 JSON，不要其他文字。"
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                    ],
                }
            ],
        )
        text = resp.choices[0].message.content or ""
        parsed = _extract_json(text)
        if parsed is None:
            parsed = {"name": "未知", "category": "", "dynasty": "", "confidence": 0.0}
        confidence = float(parsed.get("confidence", 0.5))
        name = parsed.get("name", "未知")
        return {
            "candidates": [{"exhibit_id": None, "name": name, "confidence": confidence}],
            "best_match": {"exhibit_id": None, "name": name, "confidence": confidence},
            "best_confidence": confidence,
            "raw_meta": parsed,
        }

    # === 讲解生成（文本）===

    async def generate_narration(
        self, exhibit_info: dict[str, Any], lang: str
    ) -> dict[str, Any]:
        """生成 4 角度合并的图文讲解，返回 {blocks: [...]} 结构。"""
        return await self._call_text_llm_json(exhibit_info, lang)

    async def _call_text_llm_json(
        self, exhibit_info: dict[str, Any], lang: str
    ) -> dict[str, Any]:
        lang_name = {
            "zh": "中文",
            "en": "英文",
            "ja": "日文",
            "ko": "韩文",
            "fr": "法文",
            "es": "西班牙文",
        }.get(lang, "中文")
        prompt = (
            f"你是博物馆讲解员。为以下展品生成口语化讲解（{lang_name}），适合朗读。要求：\n"
            "1. 包含四个角度：历史脉络、文物意义、铸造工艺、历史趣闻\n"
            "2. 口语化，避免长句和生僻字\n"
            '3. 不确定的地方明确说"暂无确切考证"，不要编造年代、出土地\n'
            '4. 以 JSON 返回：{"blocks":[{"type":"text","section":"历史脉络","text":"..."},...]}\n\n'
            f"展品信息：{json.dumps(exhibit_info, ensure_ascii=False)}"
        )
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content or ""
        parsed = _extract_json(content)
        if parsed is None:
            return {
                "blocks": [
                    {"type": "text", "section": "说明", "text": "讲解生成失败，请稍后重试。"}
                ]
            }
        return parsed

    # === 对话追问（文本）===

    async def chat(
        self,
        exhibit_info: dict[str, Any],
        message: str,
        lang: str,
        chat_history: list[dict[str, str]],
    ) -> str:
        return await self._call_text_llm(exhibit_info, message, lang, chat_history)

    async def _call_text_llm(
        self,
        exhibit_info: dict[str, Any],
        message: str,
        lang: str,
        chat_history: list[dict[str, str]],
    ) -> str:
        system = (
            "你是博物馆讲解员。正在讲解的展品："
            + json.dumps(exhibit_info, ensure_ascii=False)
            + f"。回答用户追问，语言：{lang}。不确定的明说，不要编造。"
        )
        messages = [{"role": "system", "content": system}] + chat_history + [
            {"role": "user", "content": message}
        ]
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return resp.choices[0].message.content or ""


# 全局单例
model_router = ModelRouter(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
    model=settings.llm_model,
)
