import re
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import feedparser
import requests

from src.config import RSS_FEEDS, FETCH_HOURS_AGO

# PubMed経由で取得するジャーナル（ACS等のRSSが利用不可の場合）
PUBMED_JOURNALS = [
    {
        "name": "Molecular Pharmaceutics",
        "query": 'Mol Pharm[jour]',
        "category": "製剤・物性解析",
        "limit": 5,
    },
    {
        "name": "Analytical Chemistry (ACS)",
        "query": 'Anal Chem[jour] AND (pharmaceutical OR drug OR formulation OR biopharmaceutical)',
        "category": "物性・分析",
        "limit": 3,
    },
]


def clean_html(raw_html: str) -> str:
    """HTMLタグや余分な空白を除去してプレーンテキストにする"""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def parse_entry_datetime(entry: Any) -> datetime | None:
    """RSSエントリから公開日時を取得してUTCのdatetimeとして返す"""
    time_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if time_struct:
        try:
            return datetime.fromtimestamp(time.mktime(time_struct), tz=timezone.utc)
        except Exception:
            pass
    return None


def fetch_pubmed_articles(journal_info: Dict[str, Any], hours_ago: int) -> List[Dict[str, Any]]:
    """NCBI eutils API を使って PubMed から最新論文を取得する（ACS等のRSS代替）"""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    headers = {"User-Agent": "CMCNewsBot/1.0 (academic research tool)"}
    limit = journal_info.get("limit", 5)
    name = journal_info["name"]
    category = journal_info.get("category", "物性・分析")

    # 期間フィルタ: reldate はここ days 日以内
    days = max(1, hours_ago // 24)
    params = {
        "db": "pubmed",
        "term": journal_info["query"],
        "retmax": limit,
        "sort": "pub date",
        "retmode": "json",
        "reldate": days,
        "datetype": "pdat",
    }

    try:
        r = requests.get(f"{base}/esearch.fcgi", params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"[WARN] PubMed esearch 失敗 ({name}): {r.status_code}")
            return []
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            print(f"[INFO] PubMed ({name}): 新着なし ({days}日以内)")
            return []

        # efetch でタイトル・DOI・概要を取得
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "rettype": "abstract",
        }
        r2 = requests.get(f"{base}/efetch.fcgi", params=fetch_params, headers=headers, timeout=20)
        if r2.status_code != 200:
            print(f"[WARN] PubMed efetch 失敗 ({name}): {r2.status_code}")
            return []

        data = r2.json()
        articles = []
        for pmid in ids:
            try:
                art = data["PubmedArticle"][ids.index(pmid)]["MedlineCitation"]["Article"]
                title = art.get("ArticleTitle", "")
                if isinstance(title, dict):
                    title = title.get("#text", str(title))
                abstract = ""
                ab_obj = art.get("Abstract", {}).get("AbstractText", "")
                if isinstance(ab_obj, list):
                    abstract = " ".join(
                        (t.get("#text", str(t)) if isinstance(t, dict) else str(t))
                        for t in ab_obj
                    )
                elif isinstance(ab_obj, dict):
                    abstract = ab_obj.get("#text", "")
                else:
                    abstract = str(ab_obj)

                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                articles.append({
                    "title": title,
                    "url": url,
                    "source": name,
                    "category": category,
                    "summary": abstract[:500],
                    "published_at": "Recent",
                })
            except Exception as ex:
                print(f"[WARN] PubMed記事パースエラー ({pmid}): {ex}")
                continue

        print(f"[INFO] PubMed ({name}): {len(articles)} 件取得")
        return articles

    except Exception as e:
        print(f"[ERROR] PubMed 取得エラー ({name}): {e}")
        return []


def fetch_recent_articles(hours_ago: int = FETCH_HOURS_AGO) -> List[Dict[str, Any]]:
    """設定されたバイオ医薬品RSSフィードから最新論文を取得する"""
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=hours_ago)

    collected_articles: List[Dict[str, Any]] = []
    seen_urls = set()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    for feed_info in RSS_FEEDS:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]
        feed_category = feed_info.get("category", "")

        try:
            response = requests.get(feed_url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"[WARN] フィード取得ステータスエラー: {feed_name} ({response.status_code})")
                continue

            parsed = feedparser.parse(response.content)

            if parsed.bozo and not parsed.entries:
                print(f"[WARN] フィードパース失敗: {feed_name} - {parsed.bozo_exception}")
                continue

            feed_count = 0
            # 学術誌は新着が少ないため、1誌あたり最大5件に制限
            max_per_feed = 5

            for entry in parsed.entries:
                if feed_count >= max_per_feed:
                    break

                url = getattr(entry, "link", "").strip()
                title = getattr(entry, "title", "").strip()
                if not url or not title or url in seen_urls:
                    continue

                pub_date = parse_entry_datetime(entry)
                # 日時がパースできて、かつ期間外ならスキップ
                if pub_date and pub_date < cutoff_time:
                    continue

                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                summary_text = clean_html(summary)[:500]

                seen_urls.add(url)
                collected_articles.append({
                    "title": title,
                    "url": url,
                    "source": feed_name,
                    "category": feed_category,
                    "summary": summary_text,
                    "published_at": pub_date.isoformat() if pub_date else "Unknown",
                })
                feed_count += 1

            print(f"[INFO] {feed_name}: {feed_count} 件取得")

        except Exception as e:
            print(f"[ERROR] フィード処理中にエラー発生 ({feed_name}): {e}")

    # PubMed経由でACS等のジャーナルを取得
    for journal_info in PUBMED_JOURNALS:
        for article in fetch_pubmed_articles(journal_info, hours_ago):
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                collected_articles.append(article)

    print(f"[INFO] 全フィードから合計 {len(collected_articles)} 件の候補論文を収集しました。")
    return collected_articles


def format_articles_for_prompt(articles: List[Dict[str, Any]]) -> str:
    """AIプロンプトに入力するためのテキスト形式に整形する"""
    if not articles:
        return "論文が見つかりませんでした。"

    formatted = []
    for i, a in enumerate(articles, 1):
        formatted.append(
            f"[{i}] タイトル: {a['title']}\n"
            f"    ジャーナル: {a['source']}\n"
            f"    カテゴリ: {a.get('category', '')}\n"
            f"    URL: {a['url']}\n"
            f"    概要: {a['summary']}\n"
        )
    return "\n".join(formatted)
