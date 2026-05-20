"""
業務ロジック。UIから直接DBを触らず、このモジュールを経由する。
返り値は辞書形式に統一し、UIが扱いやすい形で返す。
"""
from datetime import datetime
from pathlib import Path
from app.database import get_session
from app.models import Source, Modification, User, Project

# ソース種別 → repoに保存する際の拡張子
EXT_MAP = {"COBOL": ".cbl", "CL": ".cl", "その他": ".txt"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _source_name_from_filename(filename: str) -> str:
    """ファイル名からソース名を取得する（拡張子を除いて大文字化）。"""
    return Path(filename).stem.upper()


def _build_file_path(library_name: str, source_name: str, source_type: str) -> str:
    """repo内の相対パスを生成する。例: TESTLIB/SAMPLE.cbl"""
    ext = EXT_MAP.get(source_type, ".txt")
    return f"{library_name}/{source_name}{ext}"


# ─── ユーザー ─────────────────────────────────────────

def get_all_users() -> list[str]:
    """ユーザー名の一覧を返す。"""
    session = get_session()
    try:
        users = session.query(User).order_by(User.user_name).all()
        return [u.user_name for u in users]
    finally:
        session.close()


def add_user(user_name: str) -> dict:
    """ユーザーを追加する。"""
    session = get_session()
    try:
        user = User(user_name=user_name.strip(), created_at=_now())
        session.add(user)
        session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def delete_user(user_name: str) -> dict:
    """ユーザーを削除する。"""
    session = get_session()
    try:
        user = session.query(User).filter(User.user_name == user_name).first()
        if user:
            session.delete(user)
            session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ─── 案件 ─────────────────────────────────────────────

def get_active_projects() -> list[dict]:
    """アクティブな案件一覧を返す（ドロップダウン用）。"""
    session = get_session()
    try:
        projects = (
            session.query(Project)
            .filter(Project.is_active == 1)
            .order_by(Project.project_name)
            .all()
        )
        return [{"id": p.id, "name": p.project_name} for p in projects]
    finally:
        session.close()


def get_all_projects() -> list[dict]:
    """全案件（アーカイブ含む）を返す（案件管理タブ用）。"""
    session = get_session()
    try:
        projects = (
            session.query(Project)
            .order_by(Project.is_active.desc(), Project.project_name)
            .all()
        )
        result = []
        for p in projects:
            active_mod_count = (
                session.query(Modification)
                .filter(Modification.project_id == p.id, Modification.status == 1)
                .count()
            )
            result.append({
                "id": p.id,
                "name": p.project_name,
                "is_active": p.is_active,
                "active_mod_count": active_mod_count,
            })
        return result
    finally:
        session.close()


def add_project(project_name: str) -> dict:
    """案件を追加する。作成した案件のIDも返す。"""
    session = get_session()
    try:
        project = Project(project_name=project_name.strip(), created_at=_now())
        session.add(project)
        session.commit()
        return {"success": True, "project_id": project.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def archive_project(project_id: int) -> dict:
    """案件を手動でアーカイブする（非表示化）。"""
    session = get_session()
    try:
        project = session.get(Project, project_id)
        if project:
            project.is_active = 0
            session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def restore_project(project_id: int) -> dict:
    """アーカイブ済み案件を復活させる。"""
    session = get_session()
    try:
        project = session.get(Project, project_id)
        if project:
            project.is_active = 1
            session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def delete_project(project_id: int) -> dict:
    """
    案件を完全削除する（アーカイブ済みのみ可）。
    関連する修正レコードの project_id は NULL にするが、
    project_no（案件名のスナップショット）は残すため履歴は消えない。
    """
    session = get_session()
    try:
        project = session.get(Project, project_id)
        if not project:
            return {"success": False, "error": "案件が見つかりません"}
        if project.is_active == 1:
            return {"success": False, "error": "アクティブな案件は削除できません。先にアーカイブしてください"}

        # 関連修正レコードの FK を切る（案件名スナップショットは project_no に残る）
        for mod in project.modifications:
            mod.project_id = None

        session.delete(project)
        session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ─── ソース ───────────────────────────────────────────

def get_all_sources() -> list[dict]:
    """
    ソース一覧を返す。
    各ソースにはアクティブな修正中レコードのリストが含まれる。
    """
    session = get_session()
    try:
        sources = (
            session.query(Source)
            .order_by(Source.system_type, Source.library_name, Source.source_name)
            .all()
        )
        result = []
        for s in sources:
            active_mods = [m for m in s.modifications if m.status == 1]
            result.append({
                "id": s.id,
                "system_type": s.system_type,
                "library_name": s.library_name,
                "source_name": s.source_name,
                "source_type": s.source_type,
                "file_path": s.file_path or "",
                "status": "修正中" if active_mods else "空き",
                "modifiers": [
                    {
                        "id": m.id,
                        "user": m.user_name,
                        "project": m.project_no,
                        "start": m.start_datetime,
                    }
                    for m in active_mods
                ],
                "updated_at": s.updated_at or "",
            })
        return result
    finally:
        session.close()


def add_source(system_type: str, library_name: str, source_name: str, source_type: str) -> dict:
    """ソースを登録する。"""
    session = get_session()
    try:
        source = Source(
            system_type=system_type,
            library_name=library_name.strip().upper(),
            source_name=source_name.strip().upper(),
            source_type=source_type,
            updated_at=_now(),
        )
        session.add(source)
        session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def delete_source(source_id: int) -> dict:
    """ソースを削除する（修正中レコードも一緒に削除）。"""
    session = get_session()
    try:
        source = session.get(Source, source_id)
        if source:
            session.delete(source)
            session.commit()
        return {"success": True}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ─── 修正管理 ──────────────────────────────────────────

def start_modification(source_id: int, user_name: str, project_id: int) -> dict:
    """
    修正を開始する（ロックを追加）。
    project_id で案件を指定する。案件名はスナップショットとして project_no に保存する。
    """
    session = get_session()
    try:
        project = session.get(Project, project_id)
        if not project:
            return {"success": False, "error": "案件が見つかりません"}

        # 同一ソース・同一修正者・同一案件の重複チェック
        duplicate = (
            session.query(Modification)
            .filter(
                Modification.source_id == source_id,
                Modification.user_name == user_name,
                Modification.project_id == project_id,
                Modification.status == 1,
            )
            .first()
        )
        if duplicate:
            return {
                "success": False,
                "error": f"「{user_name}」は既にこのソースを「{project.project_name}」案件で修正中です",
            }

        mod = Modification(
            source_id=source_id,
            user_name=user_name,
            project_no=project.project_name,  # 案件名のスナップショット
            project_id=project_id,
            start_datetime=_now(),
            status=1,
        )
        session.add(mod)

        source = session.get(Source, source_id)
        source.updated_at = _now()

        session.commit()
        return {"success": True, "mod_id": mod.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def end_modification(mod_id: int) -> dict:
    """
    修正を終了する（自分のロックのみ解除）。
    この案件の修正中ソースが0件になった場合、案件を自動アーカイブする。
    返り値の archived_project に自動アーカイブされた案件名が入る（なければ None）。
    """
    session = get_session()
    try:
        mod = session.get(Modification, mod_id)
        if not mod:
            return {"success": False, "error": "修正レコードが見つかりません"}

        project_id = mod.project_id

        mod.status = 0
        mod.end_datetime = _now()

        source = session.get(Source, mod.source_id)
        source.updated_at = _now()

        session.commit()

        # 自動アーカイブチェック：この案件の修正中レコードが0件なら非表示にする
        archived_project_name = None
        if project_id:
            remaining = (
                session.query(Modification)
                .filter(Modification.project_id == project_id, Modification.status == 1)
                .count()
            )
            if remaining == 0:
                project = session.get(Project, project_id)
                if project and project.is_active == 1:
                    project.is_active = 0
                    session.commit()
                    archived_project_name = project.project_name

        return {"success": True, "archived_project": archived_project_name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ─── ファイルアップロード・Git連携 ────────────────────────────────

def preview_upload(
    library_name: str, source_type: str, files: list[dict]
) -> list[dict]:
    """
    アップロード前のプレビュー情報を返す。
    files: [{"filename": str, "content": bytes}]
    各ファイルが新規登録・更新・スキップ（変更なし）かを判定する。
    """
    from app import git_service

    session = get_session()
    try:
        lib = library_name.strip().upper()
        results = []
        for f in files:
            filename = f["filename"]
            content = f["content"]
            source_name = _source_name_from_filename(filename)
            existing = (
                session.query(Source)
                .filter(Source.library_name == lib, Source.source_name == source_name)
                .first()
            )

            is_new = existing is None
            is_skip = False
            is_locked = False

            if not is_new:
                # 修正中チェック（修正中のソースは一括アップロードでスキップ）
                active_mod = (
                    session.query(Modification)
                    .filter(Modification.source_id == existing.id, Modification.status == 1)
                    .first()
                )
                is_locked = active_mod is not None

                if not is_locked and existing.file_path:
                    # repoの現在の内容と比較してスキップ判定
                    current = git_service.get_file_content(existing.file_path)
                    if current is not None and current == content:
                        is_skip = True

            results.append({
                "filename":  filename,
                "source_name": source_name,
                "is_new":    is_new,
                "is_skip":   is_skip,
                "is_locked": is_locked,
            })
        return results
    finally:
        session.close()


def upload_and_register_sources(
    library_name: str,
    system_type: str,
    source_type: str,
    files: list[dict],
    commit_message: str,
    user_name: str,
) -> dict:
    """
    複数ファイルを一括登録/更新してGitコミットする。
    files: [{"filename": str, "content": bytes}, ...]
    新規ソース: DBに登録 + repoに保存
    既存ソース: repoのファイルのみ更新（DBレコードはそのまま）
    """
    from app import git_service

    session = get_session()
    try:
        lib = library_name.strip().upper()
        git_files = []
        locked_count = 0

        for f in files:
            source_name = _source_name_from_filename(f["filename"])
            rel_path = _build_file_path(lib, source_name, source_type)

            existing = (
                session.query(Source)
                .filter(Source.library_name == lib, Source.source_name == source_name)
                .first()
            )

            # 修正中のソースはスキップする
            if existing is not None:
                active_mod = (
                    session.query(Modification)
                    .filter(Modification.source_id == existing.id, Modification.status == 1)
                    .first()
                )
                if active_mod:
                    locked_count += 1
                    continue

            if existing is None:
                source = Source(
                    system_type=system_type,
                    library_name=lib,
                    source_name=source_name,
                    source_type=source_type,
                    file_path=rel_path,
                    updated_at=_now(),
                )
                session.add(source)
            else:
                existing.updated_at = _now()
                if not existing.file_path:
                    existing.file_path = rel_path

            git_files.append({"relative_path": rel_path, "content": f["content"]})

        session.commit()

        if not git_files:
            return {"success": True, "committed": 0, "skipped": 0, "locked": locked_count}

        result = git_service.save_and_commit_files(git_files, commit_message, user_name)
        result["locked"] = locked_count
        return result
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def upload_source_for_modification(
    mod_id: int,
    file_content: bytes,
    commit_message: str,
    user_name: str,
) -> dict:
    """
    修正終了時のファイルアップロード + Gitコミット。
    修正フラグの解除は end_modification が行うため、このメソッドはGitのみ担当する。
    """
    from app import git_service

    session = get_session()
    try:
        mod = session.get(Modification, mod_id)
        if not mod:
            return {"success": False, "error": "修正レコードが見つかりません"}

        source = session.get(Source, mod.source_id)
        if not source or not source.file_path:
            return {"success": False, "error": "ソースがGit管理されていません。先に一括アップロードで登録してください"}

        result = git_service.save_and_commit_files(
            [{"relative_path": source.file_path, "content": file_content}],
            commit_message,
            user_name,
        )

        if result["success"]:
            source.updated_at = _now()
            session.commit()

        return result
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()
