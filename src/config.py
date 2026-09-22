import os
from dotenv import load_dotenv

# .env ファイルが存在すれば読み込む
load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ニュース収集設定
# 学術誌は週1〜2回更新のため7日間（168時間）を対象とする
FETCH_HOURS_AGO = int(os.getenv("FETCH_HOURS_AGO", "168"))
MAX_ARTICLES = int(os.getenv("MAX_ARTICLES", "20"))

# 使用するGeminiモデル
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# バイオ医薬品・製剤（CMC）領域 RSSフィード
RSS_FEEDS = [
    # ── Elsevier (ScienceDirect) ──────────────────────────────────────
    {
        "name": "Journal of Pharmaceutical Sciences (JPharmSci)",
        "url": "https://rss.sciencedirect.com/publication/science/00223549",
        "category": "製剤・物性解析",
    },
    {
        "name": "Journal of Controlled Release (JCR)",
        "url": "https://rss.sciencedirect.com/publication/science/01683659",
        "category": "製剤・DDS",
    },
    {
        "name": "Advanced Drug Delivery Reviews (ADDR)",
        "url": "https://rss.sciencedirect.com/publication/science/0169409X",
        "category": "製剤・DDS",
    },
    {
        "name": "European Journal of Pharmaceutics and Biopharmaceutics (EJPB)",
        "url": "https://rss.sciencedirect.com/publication/science/09396411",
        "category": "製剤・物性解析",
    },
    {
        "name": "International Journal of Pharmaceutics (IJP)",
        "url": "https://rss.sciencedirect.com/publication/science/03785173",
        "category": "製剤・物性解析",
    },
    {
        "name": "Journal of Bioscience and Bioengineering (JBB)",
        "url": "https://rss.sciencedirect.com/publication/science/13891723",
        "category": "抗体・バイオプロセス",
    },
    # ── ACS (American Chemical Society) ───────────────────────────────
    {
        "name": "Molecular Pharmaceutics",
        "url": "https://pubs.acs.org/feed/mpohbp/rss/asap.xml",
        "category": "製剤・物性解析",
    },
    {
        "name": "Analytical Chemistry (ACS)",
        "url": "https://pubs.acs.org/feed/ancham/rss/asap.xml",
        "category": "物性・分析",
    },
    # ── Taylor & Francis ──────────────────────────────────────────────
    {
        "name": "mAbs",
        "url": "https://www.tandfonline.com/feed/rss/kmab20",
        "category": "抗体・バイオプロセス",
    },
    # ── Wiley ─────────────────────────────────────────────────────────
    {
        "name": "Biotechnology and Bioengineering (B&B)",
        "url": "https://onlinelibrary.wiley.com/feed/10970290/most-recent",
        "category": "抗体・バイオプロセス",
    },
]

# HF Daily Papers / Anthropic は無効（バイオ医薬領域外）
ENABLE_HF_DAILY_PAPERS = False
ENABLE_ANTHROPIC_NEWS = False

# CMC専門家向け要約プロンプト
SUMMARY_PROMPT = """
あなたはバイオ医薬品・製剤（CMC: Chemistry, Manufacturing and Controls）分野の専門リサーチアシスタントです。
以下の最新論文リストを分析し、バイオ医薬品・製剤研究者にとって最も重要な論文を選定して日本語で要約してください。

【対象読者】
バイオ医薬品（mAb、ADC、核酸医薬、遺伝子治療）および低分子製剤の研究・開発・品質（CMC）に携わる専門家。

【入力記事リスト】
{articles_text}

【選定・要約ルール】
1. 重要度・関連性が高い順に最大 {max_articles} 件を選出してください。
   優先カテゴリ:
   - 抗体医薬・バイオ製剤（凝集、粘度、安定性、ポリソルベート、HCP等）
   - 製剤化技術・DDS（ナノ粒子、LNP、リポソーム、徐放製剤）
   - 物性解析・分析（SEC-MALS、DLS、DSC、粒子測定等）
   - 品質・規制（ICH Q8-Q11、不純物、ウイルスクリアランス等）
   - バイオプロセス（細胞培養、精製、フィルトレーション等）

2. 各論文について、以下のJSON配列形式で出力してください。Markdownコードブロック ```json ... ``` で囲んでください。
3. 日本語で、専門家が短時間で内容を把握できる簡潔・正確な表現にしてください。
4. 専門用語はそのまま使用し、意訳で内容を曲げないでください。
5. "points" は3つの箇条書き（研究目的・手法、主要な結果・新知見、製剤開発・CMCへの示唆）。

【JSONフォーマット】
[
  {{
    "title_ja": "論文タイトルの日本語訳（原題に忠実に）",
    "original_title": "元の論文タイトル",
    "url": "論文のURL",
    "source": "ジャーナル名（例: JCR, mAbs, Molecular Pharmaceutics 等）",
    "category_tag": "カテゴリ（例: 製剤・DDS / 抗体・バイオプロセス / 物性・分析 / 製剤・物性解析 / 規制・CMC）",
    "points": [
      "箇条書き1: 研究の目的・背景・手法の要点",
      "箇条書き2: 主要な実験結果・新知見・数値的成果",
      "箇条書き3: 製剤開発・品質管理・CMCへの実践的示唆"
    ]
  }}
]
"""
