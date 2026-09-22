import json
import re
from typing import List, Dict, Any, Tuple
import requests

from src.config import GEMINI_API_KEY, GEMINI_MODEL, SUMMARY_PROMPT, MAX_ARTICLES
from src.fetcher import format_articles_for_prompt


def extract_json(text: str) -> List[Dict[str, Any]]:
    """Geminiの出力テキストからJSON配列を抽出・修復してパースする"""
    text = text.strip()
    
    # ```json ... ``` の除去
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()

    # 1. まず標準的なJSONパースを試行
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # 万が一 {"articles": [...]} などのキーで返ってきた場合
            for v in data.values():
                if isinstance(v, list):
                    return v
            return [data]
    except json.JSONDecodeError:
        pass

    # 2. 配列の切り出しを試行
    bracket_match = re.search(r"(\[[\s\S]*\])", text)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 途中で切れた不完全なJSONの自己修復（完成している各オブジェクトを救出）
    print("[INFO] JSONが途中で途切れている可能性があるため、完成している記事オブジェクトを救出します...")
    recovered = []
    # 各記事の {"title_ja": ... } ブロックを正規表現で個別に抽出
    object_matches = re.finditer(r'\{[^{}]*"title_ja"[\s\S]*?"points"[\s\S]*?\]\s*\}', text)
    for m in object_matches:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and obj.get("title_ja"):
                recovered.append(obj)
        except Exception:
            continue

    if recovered:
        print(f"[SUCCESS] 不完全なJSONから {len(recovered)} 件の記事を正常に救出しました！")
        return recovered

    print(f"[WARN] JSONパース・修復に失敗しました。生テキスト: {text[:200]}...")
    return []


def get_supported_models_from_api(api_key: str) -> List[str]:
    """Google AI StudioのListModels APIを呼び出し、利用可能なモデル一覧を自動取得する"""
    supported_models = []
    for version in ["v1beta", "v1"]:
        url = f"https://generativelanguage.googleapis.com/{version}/models?key={api_key}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        name = m.get("name", "").replace("models/", "")
                        if name:
                            supported_models.append(name)
                if supported_models:
                    print(f"[INFO] Google AI Studioから利用可能モデルを自動取得 ({version}): {supported_models[:6]}...")
                    break
        except Exception as e:
            print(f"[WARN] ListModels ({version}) 取得例外: {e}")

    return list(dict.fromkeys(supported_models))


def summarize_news(articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """収集した記事をGemini APIで要約・選定する。戻り値: (要約記事リスト, 使用トークン情報)"""
    if not articles:
        print("[INFO] 要約対象の記事がありません。")
        return [], {}

    api_key = GEMINI_API_KEY.strip()
    if not api_key:
        raise ValueError(
            "【設定エラー】GEMINI_API_KEY が設定されていません。\n"
            "GitHub リポジトリの [Settings] -> [Secrets and variables] -> [Actions] にて、\n"
            "Name: GEMINI_API_KEY として登録されているか確認してください。"
        )

    # APIから利用可能なモデル一覧を自動取得
    api_models = get_supported_models_from_api(api_key)
    
    # 候補モデルリストの構築（APIで実際に存在が確認されたモデルを最優先）
    candidate_models = []
    
    # 1. APIから取得したflashモデルを最優先（例: gemini-2.5-flash）
    for m in api_models:
        if "flash" in m.lower() and "tts" not in m.lower():
            candidate_models.append(m)
            
    # 2. 設定ファイルのモデル
    if GEMINI_MODEL:
        candidate_models.append(GEMINI_MODEL)
    
    # 3. その他の利用可能モデル
    for m in api_models:
        if "tts" not in m.lower():
            candidate_models.append(m)

    # 4. デフォルトのフォールバック
    candidate_models.extend(["gemini-2.5-flash", "gemini-flash-latest", "gemini-1.5-flash-latest"])
    
    # 重複排除
    models_to_try = list(dict.fromkeys(candidate_models))
    print(f"[INFO] 試行するモデル順: {models_to_try[:4]}")

    articles_text = format_articles_for_prompt(articles)
    prompt = SUMMARY_PROMPT.format(
        articles_text=articles_text,
        max_articles=MAX_ARTICLES
    )

    last_error = None
    result_data = None
    used_model = None

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,  # 十分なトークン数を確保して途切れを防止
            "responseMimeType": "application/json",  # 構造化JSONを直接出力させる
        }
    }
    headers = {"Content-Type": "application/json"}

    for model in models_to_try:
        for api_ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={api_key}"
            print(f"[INFO] Gemini API 試行中: {api_ver} / {model} ...")
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                if response.status_code == 200:
                    result_data = response.json()
                    used_model = f"{model} ({api_ver})"
                    break
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
            except Exception as e:
                last_error = str(e)
        
        if result_data:
            break

    if not result_data:
        raise RuntimeError(
            f"【Gemini API 呼び出しエラー】すべての候補モデルで失敗しました。\n"
            f"最後のエラー詳細: {last_error}\n"
            f"利用可能なモデル一覧: {api_models}\n"
            f"※APIキーが有効か、Google AI Studio で確認してください。"
        )

    try:
        raw_text = result_data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Gemini APIの応答形式が無効です: {e}, Response: {result_data}")

    # トークン使用量の取得
    usage_metadata = result_data.get("usageMetadata", {})
    usage_info = {
        "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
        "candidates_tokens": usage_metadata.get("candidatesTokenCount", 0),
        "total_tokens": usage_metadata.get("totalTokenCount", 0),
        "model": used_model,
    }

    summarized_articles = extract_json(raw_text)
    print(f"[INFO] {len(summarized_articles)} 件の重要ニュースを要約しました。")
    print(f"[INFO] 消費トークン数: {usage_info['total_tokens']} (入力: {usage_info['prompt_tokens']} / 出力: {usage_info['candidates_tokens']})")
    
    return summarized_articles, usage_info
