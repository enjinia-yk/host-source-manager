"""
Git操作ラッパー。GitPythonを使ってrepo/フォルダを管理する。
ユーザーはGitを意識せず、このモジュール経由で操作する。
"""
from git import Repo, Actor, InvalidGitRepositoryError
import config


def _get_repo() -> Repo:
    """Gitリポジトリを取得する。存在しなければ初期化する。"""
    try:
        return Repo(config.REPO_DIR)
    except InvalidGitRepositoryError:
        return _create_repo()


def _create_repo() -> Repo:
    """Gitリポジトリを新規作成し、初期コミットを作る。"""
    repo = Repo.init(config.REPO_DIR)
    # 空のリポジトリではdiff/logが動かないため、初期コミットを作成しておく
    gitkeep = config.REPO_DIR / ".gitkeep"
    gitkeep.touch()
    repo.index.add([".gitkeep"])
    repo.index.commit(
        "初期化",
        author=Actor("system", "system@hsm"),
        committer=Actor("system", "system@hsm"),
    )
    return repo


def init_repo() -> None:
    """アプリ起動時に呼ぶ。リポジトリがなければ自動作成する。"""
    _get_repo()


def save_and_commit_files(
    files: list[dict],
    commit_message: str,
    author_name: str,
) -> dict:
    """
    複数ファイルをrepoに保存してGitコミットする。

    files: [{"relative_path": "TESTLIB/SAMPLE.cbl", "content": bytes}, ...]
    """
    try:
        repo = _get_repo()
        author = Actor(author_name, f"{author_name}@hsm")

        staged = []
        for f in files:
            abs_path = config.REPO_DIR / f["relative_path"]
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_bytes(f["content"])
            staged.append(f["relative_path"])

        total = len(files)
        repo.index.add(staged)

        # HEADと比較して実際に変更されたファイル数を確認する
        try:
            changed_count = len(repo.index.diff("HEAD"))
        except Exception:
            # HEADがない（初回コミット）場合は全件変更扱い
            changed_count = total

        skipped_count = total - changed_count

        if changed_count == 0:
            return {"success": True, "committed": 0, "skipped": total}

        repo.index.commit(
            commit_message,
            author=author,
            committer=author,
        )
        return {"success": True, "committed": changed_count, "skipped": skipped_count}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_file_content(relative_path: str) -> bytes | None:
    """repoに現在保存されているファイルの内容を返す。存在しなければNone。"""
    try:
        abs_path = config.REPO_DIR / relative_path
        if abs_path.exists():
            return abs_path.read_bytes()
        return None
    except Exception:
        return None


def get_diff(relative_path: str) -> dict:
    """
    最新コミットと1つ前のコミットの差分を返す。
    初回コミット（1件のみ）の場合は追加行として表示する。
    """
    try:
        repo = _get_repo()
        commits = list(repo.iter_commits(paths=relative_path, max_count=2))

        if not commits:
            return {"success": False, "error": "このファイルのコミット履歴がありません"}

        if len(commits) == 1:
            # 初回コミット：show コマンドで追加内容を表示する
            diff = repo.git.show(
                "--format=", "--no-color", commits[0].hexsha, "--", relative_path
            ).strip()
        else:
            diff = repo.git.diff(
                "--no-color", commits[1].hexsha, commits[0].hexsha, "--", relative_path
            )

        return {"success": True, "diff": diff}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_log(relative_path: str, limit: int = 20) -> dict:
    """このファイルのコミット履歴を返す（新しい順）。"""
    try:
        repo = _get_repo()
        commits = list(repo.iter_commits(paths=relative_path, max_count=limit))

        log = [
            {
                "hash": c.hexsha[:8],
                "author": c.author.name,
                "date": c.authored_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "message": c.message.strip(),
            }
            for c in commits
        ]
        return {"success": True, "log": log}
    except Exception as e:
        return {"success": False, "error": str(e)}
