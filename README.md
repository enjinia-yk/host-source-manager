# ホストソース管理システム

社内基幹システム（IBM i）のCOBOL/CLソースを管理するWebアプリケーションです。  
誰がどのソースを修正中かを可視化し、上書き事故を防ぐことを目的としています。

## 主な機能

- **ソース一覧** — 修正中のソースを一覧表示。誰がどの案件で修正しているか確認できる
- **修正開始・終了** — 修正中ロックの管理（1ソースに複数の案件・担当者が同時修正可能）
- **案件管理** — 案件の追加・アーカイブ・削除。修正完了で自動アーカイブ
- **ユーザー管理** — ユーザーの追加・削除
- **ソース登録** — 1件手動登録と一括アップロード（Git連携）
- **差分表示・履歴表示** — Gitを使ったバージョン管理

## 技術スタック

| 分類 | 技術 |
|------|------|
| 言語 | Python 3.11+ |
| Web UI | NiceGUI |
| DB | SQLite + SQLAlchemy |
| バージョン管理 | GitPython |

## セットアップ手順

### 前提条件

- Python 3.11 以上
- Git

### 1. リポジトリをクローン

```powershell
git clone https://github.com/enjinia-yk/host-source-manager.git
cd host-source-manager
```

### 2. 仮想環境の作成とライブラリのインストール

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境設定ファイルの作成

```powershell
copy .env.example .env
```

`.env` をテキストエディタで開き、`APP_STORAGE_SECRET` を任意の文字列に変更してください。

```
APP_STORAGE_SECRET=任意のランダムな文字列
```

### 4. 起動

```powershell
python main.py
```

ブラウザで `http://localhost:8080` を開く。

> `data/`（データベース）と `repo/`（Gitリポジトリ）は初回起動時に自動作成されます。

## 初回の使い方

1. **ユーザー管理** タブでユーザーを登録する
2. 画面右上からユーザーを選択する
3. **ソース登録** タブでソースを登録する（手動1件 or 一括アップロード）
4. **ソース一覧** タブで修正開始・終了を管理する

## 注意事項

- `.env` ファイルはGit管理対象外です。各環境で個別に作成してください
- `data/`（DB）と `repo/`（Gitリポジトリ）はGit管理対象外です
