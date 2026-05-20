from sqlalchemy import Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "tblUser"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(100), unique=True, nullable=False)
    created_at = Column(String(20), nullable=False)


class Project(Base):
    """案件管理テーブル。"""

    __tablename__ = "tblProject"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_name = Column(String(200), unique=True, nullable=False)
    is_active = Column(Integer, nullable=False, default=1)  # 1:アクティブ 0:アーカイブ
    created_at = Column(String(20), nullable=False)

    modifications = relationship("Modification", back_populates="project")


class Source(Base):
    __tablename__ = "tblSource"

    id = Column(Integer, primary_key=True, autoincrement=True)
    system_type = Column(String(10), nullable=False)   # 商流 / 共配 / 本社
    library_name = Column(String(100), nullable=False)
    source_name = Column(String(100), nullable=False)
    source_type = Column(String(20), nullable=False)   # COBOL / CL など
    file_path = Column(Text)                           # Phase 2以降で使用
    updated_at = Column(String(20))

    modifications = relationship(
        "Modification", back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("library_name", "source_name", name="uq_library_source"),
    )


class Modification(Base):
    """修正中管理テーブル。1ソースに複数レコードを持てる（案件ごとに独立管理）。"""

    __tablename__ = "tblModification"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("tblSource.id"), nullable=False)
    user_name = Column(String(100), nullable=False)
    project_no = Column(String(200), nullable=False)   # 案件名のスナップショット（案件削除後も残る）
    project_id = Column(Integer, ForeignKey("tblProject.id"), nullable=True)
    start_datetime = Column(String(20), nullable=False)
    end_datetime = Column(String(20))
    status = Column(Integer, nullable=False, default=1)  # 1:修正中 0:完了
    comment = Column(Text)
    git_branch = Column(String(200))  # Phase 3以降で使用

    source = relationship("Source", back_populates="modifications")
    project = relationship("Project", back_populates="modifications")
