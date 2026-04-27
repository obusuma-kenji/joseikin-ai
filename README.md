# joseikin-ai

キャリアアップ助成金・業務改善助成金の申請支援AIポータルです。

## 構成

```
joseikin-ai/
├── app/
│   ├── api.py           # FastAPI サーバー（Renderにデプロイ）
│   ├── engine.py        # キャリアアップ助成金 判定エンジン
│   ├── gyomu_kaizen.py  # 業務改善助成金 判定エンジン
│   ├── models.py        # データモデル
│   └── render.py        # テンプレート出力
├── laws/
│   ├── career-up-guideline.pdf      # キャリアアップ助成金Q&A
│   └── gyomu-kaizen-guideline.pdf   # 業務改善助成金Q&A（追加予定）
├── templates/
│   ├── reason.txt.txt       # 申請理由文テンプレート
│   ├── documents.txt.txt    # 不足資料テンプレート
│   └── flow.txt.txt         # チェックリストテンプレート
├── index.html           # フロントエンド（GitHub Pages）
├── requirements.txt
└── render.yaml          # Renderデプロイ設定
```

## セットアップ

### ローカル（Streamlit版）
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app/main.py
```

### API サーバー（Render）
```bash
uvicorn app.api:app --reload
```

環境変数 `ANTHROPIC_API_KEY` を設定してください。

## 注意

本ツールは申請可否を最終判断するものではありません。
最終的には提出先の労働局・ハローワーク案内と最新様式に従ってください。
