"""手动联调真实大模型 glm-5.2。

运行：uv run python scripts/manual_test.py
需要：/tmp/test_ding.jpg 存在（会自动下载）
"""

import asyncio
import base64
import os
import sys

import httpx

# 把项目根（backend/）加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.model_router import model_router  # noqa: E402


async def main():
    # 准备测试图片
    img_path = "/tmp/test_ding.jpg"
    if not os.path.exists(img_path):
        print("下载测试图片...")
        resp = httpx.get(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/HouMuWuDingFullView.jpg/300px-HouMuWuDingFullView.jpg",
            timeout=30,
        )
        with open(img_path, "wb") as f:
            f.write(resp.content)

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    print(f"图片大小: {len(img_b64)} chars (base64)\n")

    # 1. 识别测试
    print("=" * 50)
    print("=== 识别测试（glm-5.2 视觉）===")
    print("=" * 50)
    result = await model_router.recognize(img_b64, museum_id=1, hint="青铜器")
    print(f"识别名称: {result['best_match']['name']}")
    print(f"置信度: {result['best_confidence']}")
    print(f"原始元数据: {result['raw_meta']}")

    # 2. 讲解生成测试
    print("\n" + "=" * 50)
    print("=== 讲解生成测试（glm-5.2 文本）===")
    print("=" * 50)
    narration = await model_router.generate_narration(
        {"name": "司母戊鼎", "category": "青铜器", "dynasty": "商代"}, "zh"
    )
    for block in narration.get("blocks", []):
        if block.get("type") == "text":
            print(f"\n【{block.get('section', '')}】")
            print(block.get("text", "")[:200])

    # 3. 对话测试
    print("\n" + "=" * 50)
    print("=== 对话测试（glm-5.2 文本）===")
    print("=" * 50)
    print("问：铭文什么意思？")
    reply = await model_router.chat(
        {"name": "司母戊鼎", "category": "青铜器", "dynasty": "商代"},
        "铭文什么意思",
        "zh",
        [],
    )
    print(f"答：{reply}")


if __name__ == "__main__":
    asyncio.run(main())
