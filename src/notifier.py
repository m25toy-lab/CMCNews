from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import requests

from src.config import DISCORD_WEBHOOK_URL


# カテゴリに応じたEmbedカラー（16進数カラーコード）
CATEGORY_COLORS = {
    "公式発表": 0xFFD700,     # Gold (一次情報・公式)
    "研究論文": 0x00CED1,     # Dark Turquoise (論文)
    "論文": 0x00CED1,         # Dark Turquoise (論文)
    "LLM": 0x7B68EE,         # Medium Slate Blue
    "画像生成": 0xFF69B4,     # Hot Pink
    "ビジネス": 0x1E90FF,     # Dodger Blue
    "規制": 0xFFA500,         # Orange
    "開発ツール": 0x32CD32,   # Lime Green
    "ハードウェア": 0x9370DB, # Medium Purple
    "デフォルト": 0x5865F2,   # Discord Blurple
}


def get_color_for_category(category: str) -> int:
    """カテゴリ名からカラーコードを取得する"""
    for key, color in CATEGORY_COLORS.items():
        if key in category:
            return color
    return CATEGORY_COLORS["デフォルト"]


def send_to_discord(
    summarized_articles: List[Dict[str, Any]],
    usage_info: Optional[Dict[str, Any]] = None
) -> bool:
    """要約されたニュース記事とAPI使用量をDiscord Webhookに送信する"""
    webhook_url = DISCORD_WEBHOOK_URL.strip()
    if not webhook_url:
        raise ValueError(
            "【設定エラー】DISCORD_WEBHOOK_URL が設定されていません。\n"
            "GitHub リポジトリの [Settings] -> [Secrets and variables] -> [Actions] にて、\n"
            "Name: DISCORD_WEBHOOK_URL として登録されているか確認してください。"
        )

    if not summarized_articles:
        print("[INFO] 送信する記事がありません。")
        return False

    # 日本時間 (JST: UTC+9) の現在日付を取得
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    date_str = now_jst.strftime("%Y/%m/%d (%a)")

    # メッセージ本文
    header_content = (
        f"🌅 **【朝刊】AI最新ニュース要約 ({date_str})**\n"
        f"通勤中・隙間時間用！本日の重要トピック {len(summarized_articles)} 選をお届けします。"
    )

    # Discord Embed の構築（最大10件まで）
    embeds = []
    for article in summarized_articles[:10]:
        title = article.get("title_ja") or article.get("original_title", "タイトルなし")
        url = article.get("url", "")
        source = article.get("source", "Web")
        category = article.get("category_tag", "AIニュース")
        points = article.get("points", [])

        # 箇条書き要約を整形
        if isinstance(points, list):
            description = "\n".join(f"• {p}" for p in points)
        else:
            description = str(points)

        embed = {
            "title": f"📌 {title}",
            "url": url,
            "description": description,
            "color": get_color_for_category(category),
            "footer": {
                "text": f"{source} | カテゴリ: {category}",
            },
        }
        embeds.append(embed)

    # トークン使用量情報の追加
    if usage_info and usage_info.get("total_tokens"):
        tokens = usage_info["total_tokens"]
        model = usage_info.get("model", "Gemini")
        footer_embed = {
            "description": f"📊 **本日のAPI使用実績**: `{tokens:,}` tokens ({model}) ｜ 無料枠運用中（1日1,500回まで無料）",
            "color": 0x2ECC71,  # Green
        }
        embeds.append(footer_embed)

    payload = {
        "username": "AI News Daily",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712038.png",
        "content": header_content,
        "embeds": embeds,
    }

    print(f"[INFO] Discord Webhook へ送信中 ({len(embeds)} 件のEmbed)...")
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
    except Exception as e:
        raise RuntimeError(f"【Discord接続エラー】Webhook URLへのリクエストが失敗しました: {e}")

    if response.status_code in [200, 204]:
        print("[SUCCESS] Discord への通知送信が完了しました！")
        return True
    else:
        print(f"[ERROR] Discord 送信失敗 ({response.status_code}): {response.text}")
        if response.status_code == 404:
            raise RuntimeError(
                f"【Discord Webhook エラー 404】Webhook URLが見つかりません。\n"
                f"URLが途中で切れていないか、チャンネルが削除されていないか確認してください。\n"
                f"現在のURL先頭: {webhook_url[:35]}..."
            )
        response.raise_for_status()
        return False
