import argparse
import os
import sys
from datetime import datetime

from src.fetcher import fetch_recent_articles
from src.summarizer import summarize_news
from src.site_builder import build_site


def main():
    # Windowsコンソール等での文字化け防止
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="CMC News Daily — バイオ医薬品論文ダイジェスト自動生成")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gemini API呼び出しとHTML生成を行わず、RSS収集のみをテストする",
    )
    parser.add_argument(
        "--test-site",
        action="store_true",
        help="ダミーデータを用いてHTMLサイト生成のみをテストする",
    )
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="HTML出力先ディレクトリ（デフォルト: docs）",
    )
    args = parser.parse_args()

    print(f"=== CMC News Daily 開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    # 1. サイト生成の単体テストモード（ダミーデータ）
    if args.test_site:
        print("[TEST] ダミーデータでHTMLサイト生成テストを実行します...")
        dummy_articles = [
            {
                "title_ja": "【テスト】ポリソルベート80の分解がmAb製剤の凝集に与える影響",
                "original_title": "Impact of Polysorbate 80 Degradation on mAb Aggregation in Biopharmaceutical Formulations",
                "url": "https://www.example.com/paper1",
                "source": "Journal of Pharmaceutical Sciences (JPharmSci)",
                "category_tag": "製剤・物性解析",
                "points": [
                    "ポリソルベート80（PS80）の酸化分解産物がmAbの凝集挙動に与える影響をSEC-MALSおよびDLSで定量的に評価した。",
                    "PS80の酸化度が5%を超えると凝集体形成速度が有意に増加（p<0.01）し、特に40℃加速試験で顕著な差が観察された。",
                    "製剤設計においてPS80含量のモニタリング頻度の見直しと、抗酸化剤（メチオニン等）の併用が品質維持に有効であることが示唆された。",
                ],
            },
            {
                "title_ja": "【テスト】LNPを用いたmRNA送達システムの製造スケールアップ最適化",
                "original_title": "Scale-up Optimization of mRNA-LNP Manufacturing Process for Biopharmaceutical Applications",
                "url": "https://www.example.com/paper2",
                "source": "Journal of Controlled Release (JCR)",
                "category_tag": "製剤・DDS",
                "points": [
                    "マイクロ流体デバイスを用いたLNP製造プロセスを10 mL/minから1 L/minへスケールアップし、粒子径・PDI・封入効率の変動要因を特定した。",
                    "流量比（FRR）3:1・全流量500 mL/minの条件でPDI<0.1・封入率>90%を再現性高く達成し、スケール間でのmRNA完全性（integrity）も維持された。",
                    "ICH Q8に基づくQbD手法を用いたDOEによりCQAに影響するCPPを特定しており、商業製造への移行設計の指針を提供する。",
                ],
            },
        ]
        build_site(dummy_articles, docs_dir=args.docs_dir)
        print(f"=== テスト完了 → {args.docs_dir}/index.html を確認してください ===")
        return

    # 2. RSSフィードから記事を収集
    articles = fetch_recent_articles()
    if not articles:
        print("[INFO] 新着論文が見つかりませんでした。終了します。")
        return

    # ドライランモード
    if args.dry_run:
        print(f"\n--- [DRY-RUN] 取得記事サンプル (全 {len(articles)} 件中 5 件表示) ---")
        for a in articles[:5]:
            print(f"- [{a['source']}] {a['title']}")
            print(f"  カテゴリ: {a.get('category', 'N/A')}")
            print(f"  URL: {a['url']}")
            print(f"  概要: {a['summary'][:100]}...\n")
        print("=== ドライラン完了（API呼び出しとHTML生成はスキップされました） ===")
        return

    # 3. Gemini APIによる重要論文の選定・要約
    summarized_articles, usage_info = summarize_news(articles)
    if not summarized_articles:
        print("[WARN] 要約結果が空でした。処理を中断します。")
        return

    print(f"[INFO] 消費トークン: {usage_info.get('total_tokens', 'N/A')} ({usage_info.get('model', 'Gemini')})")

    # 4. 静的HTMLサイトの生成
    build_site(summarized_articles, docs_dir=args.docs_dir)

    print("=== 全処理が正常に完了しました ===")


if __name__ == "__main__":
    main()
