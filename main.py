"""
ホストソース管理システム エントリーポイント
実行方法: python main.py
ブラウザで http://localhost:8080 を開く
"""
from nicegui import app, ui
import config
from app.database import init_db
from app.ui.source_list import create_main_page


@app.on_startup
async def startup():
    """アプリ起動時にDBとGitリポジトリを初期化する。"""
    init_db()
    from app import git_service
    git_service.init_repo()


@ui.page("/")
def index():
    create_main_page()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host=config.APP_HOST,
        port=config.APP_PORT,
        title=config.APP_TITLE,
        storage_secret=config.APP_STORAGE_SECRET,
        reload=False,
    )
