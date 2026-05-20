from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import config

# dataディレクトリがなければ作成する
config.DATA_DIR.mkdir(exist_ok=True)

engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    # NiceGUIはマルチスレッド環境のためこのオプションが必要
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """テーブルを作成する。アプリ起動時に1回だけ呼ぶ。"""
    from app.models import Base
    Base.metadata.create_all(engine)
    config.REPO_DIR.mkdir(exist_ok=True)
    _migrate()


def _migrate():
    """既存DBへの列追加など、後から必要になったスキーマ変更を適用する。"""
    with engine.connect() as conn:
        # tblModification に project_id 列がなければ追加する
        try:
            conn.execute(text(
                "ALTER TABLE tblModification ADD COLUMN project_id INTEGER REFERENCES tblProject(id)"
            ))
            conn.commit()
        except Exception:
            pass  # すでに存在する場合はスキップ


def get_session():
    """DBセッションを取得する。使い終わったら必ずclose()すること。"""
    return SessionLocal()
