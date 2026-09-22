"""
site_builder.py — バイオ医薬品論文ダイジェストの静的HTML生成モジュール

Gemini APIの要約結果を受け取り、GitHub Pages用の静的HTMLサイトを生成する。
- docs/index.html      : 最新日付のトップページ（毎日上書き）
- docs/archive/        : 日付ごとのアーカイブページ
"""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any


# カテゴリ → バッジの色クラス
CATEGORY_BADGE = {
    "製剤・DDS":       ("badge-dds",      "💊"),
    "製剤・物性解析":  ("badge-analysis",  "🔬"),
    "抗体・バイオプロセス": ("badge-bio",  "🧬"),
    "物性・分析":      ("badge-analysis",  "🔬"),
    "規制・CMC":       ("badge-cmc",       "📋"),
}
DEFAULT_BADGE = ("badge-default", "📄")


def _badge(category: str) -> tuple[str, str]:
    for key, val in CATEGORY_BADGE.items():
        if key in category:
            return val
    return DEFAULT_BADGE


def _article_card_html(article: Dict[str, Any], idx: int) -> str:
    """1論文分のHTMLカードを生成する"""
    title_ja = article.get("title_ja") or article.get("original_title", "タイトルなし")
    original_title = article.get("original_title", "")
    url = article.get("url", "#")
    source = article.get("source", "")
    category = article.get("category_tag", "")
    points = article.get("points", [])

    badge_cls, badge_icon = _badge(category)
    points_html = "\n".join(
        f'<li>{p}</li>' for p in points if p
    )

    return f"""
    <article class="article-card" id="article-{idx}">
      <div class="card-header">
        <span class="badge {badge_cls}">{badge_icon} {category}</span>
        <span class="source-label">{source}</span>
      </div>
      <h2 class="article-title">
        <a href="{url}" target="_blank" rel="noopener">{title_ja}</a>
      </h2>
      {f'<p class="original-title">原題: {original_title}</p>' if original_title and original_title != title_ja else ''}
      <ul class="points-list">
        {points_html}
      </ul>
      <a class="read-more" href="{url}" target="_blank" rel="noopener">原文を読む →</a>
    </article>
"""


def _css() -> str:
    return """
    :root {
      --bg: #f8f9fa;
      --card-bg: #ffffff;
      --text: #1a1a2e;
      --muted: #6c757d;
      --accent: #2563eb;
      --border: #e2e8f0;
      --dds:      #16a34a;
      --analysis: #7c3aed;
      --bio:      #0284c7;
      --cmc:      #d97706;
      --default:  #475569;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans JP", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.7;
    }
    header {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
      color: #fff;
      padding: 2rem 1rem;
      text-align: center;
    }
    header h1 { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em; }
    header p  { margin-top: 0.4rem; opacity: 0.8; font-size: 0.95rem; }
    .date-badge {
      display: inline-block;
      margin-top: 0.7rem;
      background: rgba(255,255,255,0.15);
      border-radius: 9999px;
      padding: 0.2rem 1rem;
      font-size: 0.85rem;
    }
    main {
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1rem 4rem;
    }
    .article-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.4rem 1.6rem;
      margin-bottom: 1.2rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.05);
      transition: box-shadow 0.2s;
    }
    .article-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.10); }
    .card-header {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 0.6rem;
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.7rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      color: #fff;
    }
    .badge-dds      { background: var(--dds); }
    .badge-analysis { background: var(--analysis); }
    .badge-bio      { background: var(--bio); }
    .badge-cmc      { background: var(--cmc); }
    .badge-default  { background: var(--default); }
    .source-label {
      font-size: 0.78rem;
      color: var(--muted);
      margin-left: auto;
    }
    .article-title {
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
      line-height: 1.4;
    }
    .article-title a {
      color: var(--text);
      text-decoration: none;
    }
    .article-title a:hover { color: var(--accent); text-decoration: underline; }
    .original-title {
      font-size: 0.78rem;
      color: var(--muted);
      margin-bottom: 0.6rem;
      font-style: italic;
    }
    .points-list {
      list-style: none;
      padding: 0;
      margin-bottom: 0.8rem;
    }
    .points-list li {
      padding: 0.18rem 0 0.18rem 1.2rem;
      position: relative;
      font-size: 0.9rem;
      color: #334155;
    }
    .points-list li::before {
      content: "•";
      position: absolute;
      left: 0.2rem;
      color: var(--accent);
      font-weight: bold;
    }
    .read-more {
      display: inline-block;
      font-size: 0.82rem;
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .read-more:hover { text-decoration: underline; }
    .archive-nav {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.4rem;
      margin-top: 2rem;
    }
    .archive-nav h3 {
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 0.6rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .archive-links { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .archive-links a {
      display: inline-block;
      padding: 0.25rem 0.8rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.82rem;
      color: var(--accent);
      text-decoration: none;
    }
    .archive-links a:hover { background: var(--accent); color: #fff; }
    footer {
      text-align: center;
      padding: 1.5rem;
      font-size: 0.78rem;
      color: var(--muted);
      border-top: 1px solid var(--border);
    }
    @media (max-width: 600px) {
      header h1 { font-size: 1.3rem; }
      .article-card { padding: 1rem 1.1rem; }
    }
"""


def _build_html(
    articles: List[Dict[str, Any]],
    date_str: str,
    archive_links: List[Dict[str, str]],
    title: str = "CMC News Daily",
) -> str:
    """フルHTMLページを組み立てる"""
    cards_html = "\n".join(_article_card_html(a, i + 1) for i, a in enumerate(articles))

    archive_html = ""
    if archive_links:
        links = "\n".join(
            f'<a href="{lnk["path"]}">{lnk["label"]}</a>'
            for lnk in archive_links
        )
        archive_html = f"""
        <nav class="archive-nav">
          <h3>📅 過去アーカイブ</h3>
          <div class="archive-links">{links}</div>
        </nav>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {date_str}</title>
  <style>{_css()}</style>
</head>
<body>
  <header>
    <h1>🧬 CMC News Daily</h1>
    <p>バイオ医薬品・製剤 最新論文ダイジェスト</p>
    <span class="date-badge">📅 {date_str} ／ {len(articles)} 件</span>
  </header>
  <main>
    {cards_html}
    {archive_html}
  </main>
  <footer>
    自動生成: Gemini API + GitHub Actions ／ ソース: JPharmSci, JCR, ADDR, EJPB, IJP, Molecular Pharmaceutics, mAbs, B&amp;B 等
  </footer>
</body>
</html>
"""


def _collect_existing_archives(docs_dir: str) -> List[Dict[str, str]]:
    """docs/archive/ 内の既存HTMLファイルから過去アーカイブリストを作成する"""
    archive_dir = os.path.join(docs_dir, "archive")
    links = []
    if os.path.isdir(archive_dir):
        for fname in sorted(os.listdir(archive_dir), reverse=True)[:30]:
            if fname.endswith(".html"):
                date_label = fname.replace(".html", "")
                links.append({
                    "label": date_label,
                    "path": f"archive/{fname}",
                })
    return links


def build_site(
    summarized_articles: List[Dict[str, Any]],
    docs_dir: str = "docs",
) -> None:
    """
    HTMLサイトを生成して docs/ ディレクトリに保存する。

    Args:
        summarized_articles: Gemini APIが返した要約済み論文リスト
        docs_dir: 出力先ディレクトリ（GitHub Pages ルート）
    """
    # 日本時間 (JST: UTC+9)
    jst = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst)
    date_str = now_jst.strftime("%Y-%m-%d")
    date_label = now_jst.strftime("%Y/%m/%d (%a)")

    archive_dir = os.path.join(docs_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)

    # 過去アーカイブリストを取得（新しいものから30件）
    archive_links = _collect_existing_archives(docs_dir)

    html = _build_html(
        articles=summarized_articles,
        date_str=date_label,
        archive_links=archive_links,
    )

    # ① アーカイブページを保存
    archive_path = os.path.join(archive_dir, f"{date_str}.html")
    with open(archive_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] アーカイブページを保存しました: {archive_path}")

    # ② index.html（トップページ）を上書き
    #    index.html はアーカイブへの相対パスが変わるため、archive_links の path を調整
    archive_links_for_index = [
        {"label": lnk["label"], "path": lnk["path"]}
        for lnk in archive_links
    ]
    index_html = _build_html(
        articles=summarized_articles,
        date_str=date_label,
        archive_links=archive_links_for_index,
    )
    index_path = os.path.join(docs_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"[INFO] トップページを更新しました: {index_path}")

    # ③ 要約データをJSONでも保存（将来のAPI利用や検索インデックス向け）
    json_path = os.path.join(archive_dir, f"{date_str}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date_str,
            "articles": summarized_articles,
        }, f, ensure_ascii=False, indent=2)
    print(f"[INFO] JSONデータを保存しました: {json_path}")

    print(f"[SUCCESS] サイト生成完了！ ({len(summarized_articles)} 件)")
