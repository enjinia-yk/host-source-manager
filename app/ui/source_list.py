"""
メインページのUI定義。
NiceGUIを使ってソース一覧・修正管理・ユーザー管理・ソース登録・案件管理の画面を構築する。
"""
from nicegui import app, ui
from app import source_service, git_service

SYSTEM_TYPES = ["商流", "共配", "本社"]
SOURCE_TYPES = ["COBOL", "CL", "その他"]

# 差分表示の最大文字数（大きなファイルでブラウザが重くなるのを防ぐ）
DIFF_MAX_CHARS = 10000


def create_main_page():
    """メインページ全体を構築する。NiceGUIの @ui.page から呼ばれる。"""

    # ===== ユーザー選択ダイアログ =====
    # セッションに保存されたユーザーがDBに存在しない場合はクリアする（DB初期化後などに発生）
    _users = source_service.get_all_users()
    _stored_user = app.storage.user.get("current_user")
    if _stored_user and _stored_user not in _users:
        app.storage.user.pop("current_user", None)
        _stored_user = None

    with ui.dialog() as user_dialog, ui.card().classes("w-80"):
        ui.label("ユーザー選択").classes("text-h6")
        ui.separator()

        user_select = ui.select(
            options=_users,
            label="ユーザー名",
            value=_stored_user,
        ).classes("w-full")

        ui.label(
            "ユーザーがない場合は「ユーザー管理」タブから追加してください"
        ).classes("text-caption text-grey-6 q-mt-sm")

        def _do_select_user():
            if user_select.value:
                app.storage.user["current_user"] = user_select.value
                user_label.set_text(f"ユーザー: {user_select.value}")
            user_dialog.close()

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("OK", on_click=_do_select_user, color="primary")

    # ===== ヘッダー =====
    with ui.header(elevated=True).classes("bg-indigo-8 text-white items-center gap-3"):
        ui.icon("dns").classes("text-2xl")
        ui.label("ホストソース管理システム").classes("text-h6")
        ui.space()
        current = _stored_user or ""
        user_label = ui.label(
            f"ユーザー: {current}" if current else "ユーザー未選択"
        ).classes("text-subtitle2")
        (
            ui.button("", icon="manage_accounts", on_click=user_dialog.open)
            .props("flat round color=white")
            .tooltip("ユーザー変更")
        )

    # ===== タブ =====
    with ui.tabs().classes("w-full bg-grey-2 text-indigo-8") as tabs:
        tab_source = ui.tab("ソース一覧", icon="list_alt")
        tab_proj   = ui.tab("案件管理",   icon="assignment")
        tab_user   = ui.tab("ユーザー管理", icon="people")
        tab_reg    = ui.tab("ソース登録",  icon="add_box")

    with ui.tab_panels(tabs, value=tab_source).classes("w-full"):

        # ─── ソース一覧タブ ───────────────────────────────
        with ui.tab_panel(tab_source):

            filter_state = {"text": "", "system_type": "全て", "status": "全て", "project": "全て"}
            _proj_select_ref = [None]

            @ui.refreshable
            def source_table_view():
                all_sources = source_service.get_all_sources()

                sources = all_sources
                text = filter_state["text"].upper()
                if text:
                    sources = [
                        s for s in sources
                        if text in s["library_name"] or text in s["source_name"]
                    ]
                if filter_state["system_type"] != "全て":
                    sources = [s for s in sources if s["system_type"] == filter_state["system_type"]]
                if filter_state["status"] != "全て":
                    sources = [s for s in sources if s["status"] == filter_state["status"]]
                if filter_state["project"] != "全て":
                    sources = [
                        s for s in sources
                        if any(m["project"] == filter_state["project"] for m in s["modifiers"])
                    ]

                # テーブル更新のたびに案件フィルタの選択肢も最新化する
                if _proj_select_ref[0] is not None:
                    active = source_service.get_active_projects()
                    new_opts = ["全て"] + [p["name"] for p in active]
                    _proj_select_ref[0].options = new_opts
                    _proj_select_ref[0].update()

                if not all_sources:
                    ui.label(
                        "ソースが登録されていません。「ソース登録」タブから追加してください。"
                    ).classes("text-grey q-pa-lg")
                    return
                if not sources:
                    ui.label("検索条件に一致するソースがありません。").classes("text-grey q-pa-lg")
                    return

                columns = [
                    {"name": "status",       "label": "状態",       "field": "status",       "align": "center"},
                    {"name": "system_type",  "label": "システム",   "field": "system_type",  "align": "left"},
                    {"name": "library_name", "label": "ライブラリ", "field": "library_name", "align": "left"},
                    {"name": "source_name",  "label": "ソース名",   "field": "source_name",  "align": "left"},
                    {"name": "source_type",  "label": "種別",       "field": "source_type",  "align": "center"},
                    {"name": "modifiers_str","label": "修正者（案件）","field": "modifiers_str","align": "left"},
                    {"name": "updated_at",   "label": "更新日時",   "field": "updated_at",   "align": "left"},
                    {"name": "actions",      "label": "操作",       "field": "id",           "align": "center", "sortable": False},
                ]

                rows = []
                for s in sources:
                    mod_str = "、".join(
                        f"{m['user']}({m['project']})" for m in s["modifiers"]
                    )
                    rows.append({**s, "modifiers_str": mod_str})

                table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

                table.add_slot("body-cell-status", r"""
                    <q-td :props="props">
                        <q-badge
                            :color="props.value === '修正中' ? 'orange' : 'green'"
                            :label="props.value"
                        />
                    </q-td>
                """)

                table.add_slot("body-cell-actions", r"""
                    <q-td :props="props">
                        <q-btn dense flat color="primary" icon="edit" label="修正開始"
                            @click="$parent.$emit('start_mod', props.row)"
                            class="q-mr-xs" />
                        <q-btn dense flat color="negative" icon="check_circle" label="修正終了"
                            @click="$parent.$emit('end_mod', props.row)"
                            class="q-mr-xs" />
                        <q-btn dense flat color="teal" icon="compare"
                            @click="$parent.$emit('show_diff', props.row)"
                            :disable="!props.row.file_path"
                            class="q-mr-xs">
                            <q-tooltip>差分表示</q-tooltip>
                        </q-btn>
                        <q-btn dense flat color="indigo" icon="history"
                            @click="$parent.$emit('show_history', props.row)"
                            :disable="!props.row.file_path">
                            <q-tooltip>履歴表示</q-tooltip>
                        </q-btn>
                    </q-td>
                """)

                table.on("start_mod",    lambda e: _show_start_dialog(e.args, source_table_view.refresh, proj_refresh))
                table.on("end_mod",      lambda e: _show_end_dialog(e.args, source_table_view.refresh, proj_refresh))
                table.on("show_diff",    lambda e: _show_diff_dialog(e.args))
                table.on("show_history", lambda e: _show_history_dialog(e.args))

            def _on_filter_change(key):
                def handler(e):
                    filter_state[key] = e.value if e.value is not None else ""
                    source_table_view.refresh()
                return handler

            with ui.row().classes("items-center q-pa-md q-pb-xs"):
                ui.label("ソース一覧").classes("text-h6")
                ui.space()
                ui.button("更新", icon="refresh", on_click=source_table_view.refresh).props("flat")

            with ui.row().classes("q-px-md q-pb-md gap-3 items-center flex-wrap"):
                ui.input(
                    placeholder="ライブラリ名・ソース名で検索",
                    on_change=_on_filter_change("text"),
                ).props("outlined dense clearable").classes("w-64")
                ui.select(
                    ["全て"] + SYSTEM_TYPES, value="全て", label="システム",
                    on_change=_on_filter_change("system_type"),
                ).props("outlined dense").classes("w-28")
                ui.select(
                    ["全て", "空き", "修正中"], value="全て", label="状態",
                    on_change=_on_filter_change("status"),
                ).props("outlined dense").classes("w-28")
                proj_select = ui.select(
                    ["全て"] + [p["name"] for p in source_service.get_active_projects()],
                    value="全て", label="案件",
                    on_change=_on_filter_change("project"),
                ).props("outlined dense").classes("w-40")
                _proj_select_ref[0] = proj_select

            source_table_view()

        # ─── 案件管理タブ ──────────────────────────────────
        with ui.tab_panel(tab_proj):
            proj_refresh = _build_project_panel(source_table_view.refresh)

        # ─── ユーザー管理タブ ──────────────────────────────
        with ui.tab_panel(tab_user):
            _build_user_panel(user_select)

        # ─── ソース登録タブ ────────────────────────────────
        with ui.tab_panel(tab_reg):
            _build_registration_panel(source_table_view.refresh)

    if not current:
        ui.timer(0.3, user_dialog.open, once=True)


# ─── 修正開始ダイアログ ──────────────────────────────────────────

def _show_start_dialog(source_row: dict, refresh_fn, proj_refresh_fn=None):
    current_user = app.storage.user.get("current_user", "")
    if not current_user:
        ui.notify("先にユーザーを選択してください", type="warning")
        return

    source_id = source_row["id"]
    lib = source_row["library_name"]
    src = source_row["source_name"]
    modifiers = source_row.get("modifiers", [])

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"修正開始: {lib} / {src}").classes("text-h6")
        ui.separator()

        if modifiers:
            with ui.card().classes("bg-orange-1 w-full q-pa-sm q-my-sm"):
                ui.label("⚠️ このソースは現在修正中です").classes("text-orange-9 text-bold")
                for m in modifiers:
                    ui.label(f"　・{m['user']}（{m['project']}）").classes("text-sm")
            ui.label(
                "続行すると同時修正になります。担当者と事前に確認してください。"
            ).classes("text-caption text-grey-7")

        ui.label("案件").classes("text-caption text-grey-7 q-mt-md")
        active_projects = source_service.get_active_projects()
        options = {p["id"]: p["name"] for p in active_projects}

        project_select = ui.select(
            options=options,
            label="案件を選択",
            value=list(options.keys())[0] if options else None,
        ).classes("w-full")

        if not options:
            ui.label(
                "アクティブな案件がありません。下の欄から新しい案件を作成してください。"
            ).classes("text-caption text-orange-8")

        with ui.expansion("新しい案件を追加", icon="add_circle").classes("w-full q-mt-xs"):
            new_proj_input = ui.input("案件名", placeholder="決算対応2024").classes("w-full")

            def _add_project():
                name = new_proj_input.value.strip()
                if not name:
                    ui.notify("案件名を入力してください", type="warning")
                    return
                result = source_service.add_project(name)
                if result["success"]:
                    new_id = result["project_id"]
                    updated = source_service.get_active_projects()
                    project_select.options = {p["id"]: p["name"] for p in updated}
                    project_select.value = new_id
                    project_select.update()
                    new_proj_input.value = ""
                    ui.notify(f"案件「{name}」を追加して選択しました", type="positive")
                else:
                    ui.notify(f"エラー: {result['error']}", type="negative")

            ui.button("追加して選択", on_click=_add_project, color="primary").classes("q-mt-xs")

        def _do_start():
            if not project_select.value:
                ui.notify("案件を選択または作成してください", type="warning")
                return
            result = source_service.start_modification(source_id, current_user, project_select.value)
            if result["success"]:
                ui.notify("修正開始しました", type="positive")
                dialog.close()
                refresh_fn()
                if proj_refresh_fn:
                    proj_refresh_fn()
            else:
                ui.notify(f"エラー: {result['error']}", type="negative")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("キャンセル", on_click=dialog.close).props("flat")
            btn_color = "warning" if modifiers else "primary"
            ui.button("修正開始", on_click=_do_start, color=btn_color)

    dialog.open()


# ─── 修正終了ダイアログ ──────────────────────────────────────────

def _show_end_dialog(source_row: dict, refresh_fn, proj_refresh_fn=None):
    current_user = app.storage.user.get("current_user", "")
    lib = source_row["library_name"]
    src = source_row["source_name"]
    modifiers = source_row.get("modifiers", [])
    my_mods = [m for m in modifiers if m["user"] == current_user]

    if not my_mods:
        ui.notify(
            f"あなた（{current_user}）のこのソースへの修正はありません",
            type="info",
        )
        return

    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"修正終了: {lib} / {src}").classes("text-h6")
        ui.separator()

        options = {m["id"]: f"{m['project']}　（開始: {m['start']}）" for m in my_mods}
        mod_select = ui.select(
            options=options, label="終了する修正",
            value=list(options.keys())[0],
        ).classes("w-full q-mt-md")

        # 修正後ファイルのアップロード（任意）
        uploaded_file = [None]  # (filename, content_bytes) or None

        with ui.expansion("修正後ファイルをアップロード（任意）", icon="upload_file").classes("w-full q-mt-sm"):
            upload_status = ui.label("ファイルが選択されていません").classes("text-grey-6 text-sm")

            async def _handle_upload(e):
                content = await e.file.read()
                uploaded_file[0] = (e.file.name, content)
                upload_status.set_text(f"✅ {e.file.name}")

            ui.upload(
                on_upload=_handle_upload,
                multiple=False,
                auto_upload=True,
                label="ファイルを選択",
            ).props("outlined accept='*'").classes("w-full q-mt-xs")

            commit_msg_input = ui.input(
                "コミットメッセージ（任意）",
                placeholder=f"{src} 修正",
            ).classes("w-full q-mt-sm")

        def _do_end():
            mod_id = mod_select.value

            # ファイルアップロードがある場合は先にGitコミット
            if uploaded_file[0] is not None:
                filename, content = uploaded_file[0]
                msg = commit_msg_input.value.strip() or f"{src} 修正"
                upload_result = source_service.upload_source_for_modification(
                    mod_id, content, msg, current_user
                )
                if not upload_result["success"]:
                    ui.notify(f"Gitコミットエラー: {upload_result['error']}", type="warning")
                elif upload_result.get("skipped"):
                    ui.notify("ファイルの内容に変更がないためGitコミットをスキップしました", type="info")

            # 修正フラグ解除
            result = source_service.end_modification(mod_id)
            if result["success"]:
                ui.notify("修正終了しました", type="positive")
                if result.get("archived_project"):
                    ui.notify(
                        f"案件「{result['archived_project']}」の修正がすべて完了したためアーカイブしました",
                        type="info",
                        timeout=5000,
                    )
                dialog.close()
                refresh_fn()
                if proj_refresh_fn:
                    proj_refresh_fn()
            else:
                ui.notify(f"エラー: {result['error']}", type="negative")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("キャンセル", on_click=dialog.close).props("flat")
            ui.button("修正終了", on_click=_do_end, color="negative")

    dialog.open()


# ─── 差分表示ダイアログ ──────────────────────────────────────────

def _show_diff_dialog(source_row: dict):
    lib = source_row["library_name"]
    src = source_row["source_name"]
    file_path = source_row.get("file_path", "")

    if not file_path:
        ui.notify("このソースはまだGit管理されていません", type="info")
        return

    result = git_service.get_diff(file_path)

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-4xl"):
        with ui.row().classes("items-center w-full"):
            ui.label(f"差分: {lib} / {src}").classes("text-h6")
            ui.space()
            ui.label("（最新コミット vs 1つ前）").classes("text-caption text-grey-6")

        ui.separator()

        if not result["success"]:
            ui.label(f"エラー: {result['error']}").classes("text-negative q-pa-md")
        elif not result.get("diff", "").strip():
            ui.label("差分がありません（変更なし、または初回登録のみ）").classes("text-grey q-pa-md")
        else:
            diff_text = result["diff"]
            truncated = len(diff_text) > DIFF_MAX_CHARS
            if truncated:
                diff_text = diff_text[:DIFF_MAX_CHARS]
                ui.label(f"※ 表示が長いため先頭 {DIFF_MAX_CHARS} 文字のみ表示しています").classes(
                    "text-caption text-orange-8 q-mb-sm"
                )
            ui.code(diff_text, language="diff").classes("w-full text-sm")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("閉じる", on_click=dialog.close)

    dialog.open()


# ─── 履歴表示ダイアログ ──────────────────────────────────────────

def _show_history_dialog(source_row: dict):
    lib = source_row["library_name"]
    src = source_row["source_name"]
    file_path = source_row.get("file_path", "")

    if not file_path:
        ui.notify("このソースはまだGit管理されていません", type="info")
        return

    result = git_service.get_log(file_path)

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
        ui.label(f"履歴: {lib} / {src}").classes("text-h6")
        ui.separator()

        if not result["success"]:
            ui.label(f"エラー: {result['error']}").classes("text-negative q-pa-md")
        elif not result.get("log"):
            ui.label("コミット履歴がありません").classes("text-grey q-pa-md")
        else:
            columns = [
                {"name": "date",    "label": "日時",               "field": "date",    "align": "left"},
                {"name": "author",  "label": "作者",               "field": "author",  "align": "left"},
                {"name": "message", "label": "コミットメッセージ", "field": "message", "align": "left"},
                {"name": "hash",    "label": "ハッシュ",           "field": "hash",    "align": "left"},
            ]
            ui.table(columns=columns, rows=result["log"], row_key="hash").classes("w-full")

        with ui.row().classes("justify-end q-mt-md"):
            ui.button("閉じる", on_click=dialog.close)

    dialog.open()


# ─── 案件管理パネル ──────────────────────────────────────────────

def _build_project_panel(source_refresh_fn=None):

    def _do_archive(pid, pname):
        result = source_service.archive_project(pid)
        if result["success"]:
            ui.notify(f"案件「{pname}」をアーカイブしました", type="info")
            project_list_view.refresh()
            if source_refresh_fn:
                source_refresh_fn()
        else:
            ui.notify(f"エラー: {result['error']}", type="negative")

    def _do_restore(pid, pname):
        result = source_service.restore_project(pid)
        if result["success"]:
            ui.notify(f"案件「{pname}」を復活しました", type="positive")
            project_list_view.refresh()
            if source_refresh_fn:
                source_refresh_fn()
        else:
            ui.notify(f"エラー: {result['error']}", type="negative")

    def _do_delete(pid, pname):
        result = source_service.delete_project(pid)
        if result["success"]:
            ui.notify(f"案件「{pname}」を削除しました", type="positive")
            project_list_view.refresh()
            if source_refresh_fn:
                source_refresh_fn()
        else:
            ui.notify(f"エラー: {result['error']}", type="negative")

    @ui.refreshable
    def project_list_view():
        projects = source_service.get_all_projects()
        active   = [p for p in projects if p["is_active"]]
        archived = [p for p in projects if not p["is_active"]]

        ui.label("アクティブな案件").classes("text-subtitle1 text-bold q-mb-xs")
        if not active:
            ui.label("アクティブな案件はありません").classes("text-grey q-mb-lg")
        else:
            with ui.list().props("bordered separator").classes("w-full max-w-lg q-mb-lg"):
                for p in active:
                    with ui.item():
                        with ui.item_section():
                            ui.item_label(p["name"])
                            ui.item_label(f"修正中: {p['active_mod_count']}件").props("caption")
                        with ui.item_section().props("side"):
                            (
                                ui.button(
                                    "アーカイブ", icon="archive",
                                    on_click=lambda _, pid=p["id"], pname=p["name"]: _do_archive(pid, pname),
                                ).props("flat dense color=grey")
                            )

        if archived:
            ui.separator().classes("q-my-md")
            ui.label("アーカイブ済み").classes("text-subtitle1 text-bold q-mb-xs")
            with ui.list().props("bordered separator").classes("w-full max-w-lg"):
                for p in archived:
                    with ui.item():
                        with ui.item_section():
                            ui.item_label(p["name"]).classes("text-grey-6")
                        with ui.item_section().props("side"):
                            with ui.row().classes("gap-1"):
                                (
                                    ui.button(
                                        "復活", icon="restore",
                                        on_click=lambda _, pid=p["id"], pname=p["name"]: _do_restore(pid, pname),
                                    ).props("flat dense color=positive")
                                )
                                (
                                    ui.button(
                                        "削除", icon="delete",
                                        on_click=lambda _, pid=p["id"], pname=p["name"]: _do_delete(pid, pname),
                                    ).props("flat dense color=negative")
                                )

    ui.label("案件管理").classes("text-h6 q-pa-md q-pb-xs")
    ui.separator()

    with ui.row().classes("q-pa-md gap-2 items-center"):
        new_proj_input = ui.input("新しい案件名", placeholder="決算対応2024").classes("w-64")

        def _add():
            name = new_proj_input.value.strip()
            if not name:
                ui.notify("案件名を入力してください", type="warning")
                return
            result = source_service.add_project(name)
            if result["success"]:
                ui.notify(f"案件「{name}」を追加しました", type="positive")
                new_proj_input.value = ""
                project_list_view.refresh()
                if source_refresh_fn:
                    source_refresh_fn()
            else:
                ui.notify(f"エラー: {result['error']}", type="negative")

        ui.button("追加", on_click=_add, icon="add", color="primary")

    ui.label(
        "※ 修正中のソースが全て完了すると自動的にアーカイブされます"
    ).classes("text-caption text-grey-6 q-px-md")

    with ui.column().classes("q-pa-md"):
        project_list_view()

    return project_list_view.refresh


# ─── ユーザー管理パネル ──────────────────────────────────────────

def _build_user_panel(user_select_widget=None):

    @ui.refreshable
    def user_list_view():
        users = source_service.get_all_users()
        if not users:
            ui.label("ユーザーが登録されていません").classes("text-grey q-pa-md")
            return

        with ui.list().props("bordered separator").classes("w-full max-w-sm"):
            for u in users:
                with ui.item():
                    with ui.item_section():
                        ui.item_label(u)
                    with ui.item_section().props("side"):
                        def _delete(name=u):
                            result = source_service.delete_user(name)
                            if result["success"]:
                                ui.notify(f"{name} を削除しました", type="positive")
                                user_list_view.refresh()
                                if user_select_widget is not None:
                                    user_select_widget.options = source_service.get_all_users()
                                    user_select_widget.update()
                            else:
                                ui.notify(f"エラー: {result['error']}", type="negative")

                        (
                            ui.button("", icon="delete", on_click=_delete, color="negative")
                            .props("flat round dense")
                            .tooltip(f"{u} を削除")
                        )

    ui.label("ユーザー管理").classes("text-h6 q-pa-md q-pb-xs")
    ui.separator()

    with ui.row().classes("items-center q-pa-md q-pb-xs gap-2"):
        new_user_input = ui.input("新しいユーザー名", placeholder="山田太郎").classes("w-64")

        def _add_user():
            name = new_user_input.value.strip()
            if not name:
                ui.notify("ユーザー名を入力してください", type="warning")
                return
            result = source_service.add_user(name)
            if result["success"]:
                ui.notify(f"「{name}」を追加しました", type="positive")
                new_user_input.value = ""
                user_list_view.refresh()
                if user_select_widget is not None:
                    user_select_widget.options = source_service.get_all_users()
                    user_select_widget.update()
            else:
                ui.notify(f"エラー: {result['error']}", type="negative")

        ui.button("追加", on_click=_add_user, icon="person_add", color="primary")

    with ui.column().classes("q-pa-md"):
        user_list_view()


# ─── ソース登録パネル ────────────────────────────────────────────

def _build_registration_panel(source_refresh_fn=None):

    filter_state = {"text": "", "system_type": "全て"}

    @ui.refreshable
    def registered_sources_view():
        all_sources = source_service.get_all_sources()

        sources = all_sources
        text = filter_state["text"].upper()
        if text:
            sources = [
                s for s in sources
                if text in s["library_name"] or text in s["source_name"]
            ]
        if filter_state["system_type"] != "全て":
            sources = [s for s in sources if s["system_type"] == filter_state["system_type"]]

        if not all_sources:
            ui.label("ソースが登録されていません").classes("text-grey q-pa-md")
            return
        if not sources:
            ui.label("検索条件に一致するソースがありません。").classes("text-grey q-pa-md")
            return

        columns = [
            {"name": "system_type",  "label": "システム",   "field": "system_type",  "align": "left"},
            {"name": "library_name", "label": "ライブラリ", "field": "library_name", "align": "left"},
            {"name": "source_name",  "label": "ソース名",   "field": "source_name",  "align": "left"},
            {"name": "source_type",  "label": "種別",       "field": "source_type",  "align": "center"},
            {"name": "status",       "label": "状態",       "field": "status",       "align": "center"},
            {"name": "git",          "label": "Git",        "field": "file_path",    "align": "center"},
            {"name": "del",          "label": "削除",       "field": "id",           "align": "center", "sortable": False},
        ]
        rows = [
            {
                "id": s["id"],
                "system_type": s["system_type"],
                "library_name": s["library_name"],
                "source_name": s["source_name"],
                "source_type": s["source_type"],
                "status": s["status"],
                "file_path": s["file_path"],
            }
            for s in sources
        ]

        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

        # Git管理状態をアイコンで表示
        table.add_slot("body-cell-git", r"""
            <q-td :props="props">
                <q-icon v-if="props.value" name="check_circle" color="teal" size="sm">
                    <q-tooltip>Git管理済み</q-tooltip>
                </q-icon>
                <q-icon v-else name="radio_button_unchecked" color="grey" size="sm">
                    <q-tooltip>未登録</q-tooltip>
                </q-icon>
            </q-td>
        """)

        table.add_slot("body-cell-del", r"""
            <q-td :props="props">
                <q-btn dense flat color="negative" icon="delete"
                    @click="$parent.$emit('delete_source', props.row)"
                    :disable="props.row.status === '修正中'" />
            </q-td>
        """)

        def _on_delete(e):
            row = e.args
            result = source_service.delete_source(row["id"])
            if result["success"]:
                ui.notify(
                    f"{row['library_name']}/{row['source_name']} を削除しました",
                    type="positive",
                )
                registered_sources_view.refresh()
                if source_refresh_fn:
                    source_refresh_fn()
            else:
                ui.notify(f"エラー: {result['error']}", type="negative")

        table.on("delete_source", _on_delete)

    def _on_filter_change(key):
        def handler(e):
            filter_state[key] = e.value if e.value is not None else ""
            registered_sources_view.refresh()
        return handler

    ui.label("ソース登録").classes("text-h6 q-pa-md q-pb-xs")
    ui.separator()

    with ui.row().classes("w-full q-pa-sm gap-4 items-start"):

        # ── 左側: 登録フォーム（タブ切り替え） ──────────────────
        with ui.column().style("width: 420px; flex-shrink: 0"):

            with ui.tabs().classes("w-full bg-grey-2 text-indigo-8") as reg_tabs:
                tab_manual = ui.tab("1件登録", icon="edit_note")
                tab_bulk   = ui.tab("一括アップロード", icon="upload_file")

            with ui.tab_panels(reg_tabs, value=tab_manual).classes("w-full"):

                # ── 1件登録タブ ───────────────────────────────
                with ui.tab_panel(tab_manual):
                    with ui.column().classes("w-full q-pa-sm gap-2"):
                        system_select = ui.select(SYSTEM_TYPES, label="システム種別", value=SYSTEM_TYPES[0]).classes("w-full")
                        library_input = ui.input("ライブラリ名", placeholder="TESTLIB").classes("w-full")
                        source_input  = ui.input("ソース名",     placeholder="SAMPLE").classes("w-full")
                        type_select   = ui.select(SOURCE_TYPES, label="ソース種別", value=SOURCE_TYPES[0]).classes("w-full")

                        def _add_source():
                            lib = library_input.value.strip()
                            src = source_input.value.strip()
                            if not lib or not src:
                                ui.notify("ライブラリ名とソース名を入力してください", type="warning")
                                return
                            result = source_service.add_source(system_select.value, lib, src, type_select.value)
                            if result["success"]:
                                ui.notify(f"{lib.upper()}/{src.upper()} を登録しました", type="positive")
                                library_input.value = ""
                                source_input.value  = ""
                                registered_sources_view.refresh()
                                if source_refresh_fn:
                                    source_refresh_fn()
                            else:
                                ui.notify(f"エラー: {result['error']}", type="negative")

                        ui.button("登録", on_click=_add_source, icon="add", color="primary")

                # ── 一括アップロードタブ ──────────────────────
                with ui.tab_panel(tab_bulk):
                    with ui.column().classes("w-full q-pa-sm gap-2"):
                        ui.label(
                            "ライブラリ・種別を選択してファイルをアップロードすると、"
                            "DB登録とGitコミットを同時に行います。"
                            "既存ソースは新バージョンとして更新されます。"
                        ).classes("text-caption text-grey-7")

                        ul_system = ui.select(SYSTEM_TYPES, label="システム種別", value=SYSTEM_TYPES[0]).classes("w-full")
                        ul_library = ui.input(
                            "ライブラリ名", placeholder="TESTLIB",
                            on_change=lambda e: upload_preview.refresh(),
                        ).classes("w-full")
                        ul_type = ui.select(
                            SOURCE_TYPES, label="ソース種別", value=SOURCE_TYPES[0],
                            on_change=lambda e: upload_preview.refresh(),
                        ).classes("w-full")

                        pending_files = []  # (filename, content_bytes)

                        def _remove_pending_file(filename):
                            pending_files[:] = [f for f in pending_files if f[0] != filename]
                            upload_preview.refresh()

                        @ui.refreshable
                        def upload_preview():
                            if not pending_files:
                                ui.label("ファイルが選択されていません").classes("text-grey-6 text-sm")
                                return
                            lib = ul_library.value.strip().upper()
                            if not lib:
                                ui.label("ライブラリ名を入力してください").classes("text-orange-8 text-sm")
                                return
                            preview = source_service.preview_upload(
                                lib, ul_type.value,
                                [{"filename": f[0], "content": f[1]} for f in pending_files],
                            )
                            cols = [
                                {"name": "filename",    "label": "ファイル名", "field": "filename",    "align": "left"},
                                {"name": "source_name", "label": "ソース名",   "field": "source_name", "align": "left"},
                                {"name": "status",      "label": "状態",       "field": "status",      "align": "center"},
                                {"name": "remove",      "label": "",           "field": "filename",    "align": "center", "sortable": False},
                            ]

                            def _status(p):
                                if p["is_locked"]: return "🔒 修正中（スキップ）"
                                if p["is_new"]:    return "✨ 新規登録"
                                if p["is_skip"]:   return "⏭️ スキップ"
                                return "🔄 更新"

                            rows = [
                                {"filename": p["filename"], "source_name": p["source_name"], "status": _status(p)}
                                for p in preview
                            ]
                            table = ui.table(columns=cols, rows=rows, row_key="filename").classes("w-full")
                            table.add_slot("body-cell-status", r"""
                                <q-td :props="props">
                                    <span :class="props.value.includes('修正中') ? 'text-red-8'
                                                : props.value.includes('新規') ? 'text-green-8'
                                                : props.value.includes('スキップ') ? 'text-grey-6'
                                                : 'text-orange-8'">
                                        {{ props.value }}
                                    </span>
                                </q-td>
                            """)
                            table.add_slot("body-cell-remove", r"""
                                <q-td :props="props">
                                    <q-btn dense flat color="negative" icon="close"
                                        @click="$parent.$emit('remove_file', props.row)" />
                                </q-td>
                            """)
                            table.on("remove_file", lambda e: _remove_pending_file(e.args["filename"]))

                        async def _handle_upload(e):
                            filename = e.file.name
                            content = await e.file.read()
                            existing = next((i for i, f in enumerate(pending_files) if f[0] == filename), None)
                            if existing is not None:
                                pending_files[existing] = (filename, content)
                            else:
                                pending_files.append((filename, content))
                            upload_widget.reset()
                            upload_preview.refresh()

                        upload_widget = ui.upload(
                            multiple=True,
                            on_upload=_handle_upload,
                            auto_upload=True,
                            label="ファイルを選択（複数可）",
                        ).props("outlined accept='*'").classes("w-full")

                        upload_preview()

                        ul_commit_msg = ui.input(
                            "コミットメッセージ", placeholder="TESTLIB 一括取り込み"
                        ).classes("w-full")

                        def _do_commit():
                            if not pending_files:
                                ui.notify("ファイルが選択されていません", type="warning")
                                return
                            lib = ul_library.value.strip()
                            if not lib:
                                ui.notify("ライブラリ名を入力してください", type="warning")
                                return
                            current_user = app.storage.user.get("current_user", "system")
                            msg = ul_commit_msg.value.strip() or f"{lib.upper()} 一括取り込み"
                            files_data = [{"filename": f[0], "content": f[1]} for f in pending_files]
                            result = source_service.upload_and_register_sources(
                                lib, ul_system.value, ul_type.value, files_data, msg, current_user
                            )
                            if result["success"]:
                                committed = result.get("committed", 0)
                                skipped   = result.get("skipped", 0)
                                locked    = result.get("locked", 0)
                                parts = []
                                if committed > 0: parts.append(f"{committed}件を登録/更新")
                                if skipped > 0:   parts.append(f"{skipped}件は変更なしでスキップ")
                                if locked > 0:    parts.append(f"{locked}件は修正中のためスキップ")
                                ui.notify("、".join(parts), type="positive" if committed > 0 else "info")
                                pending_files.clear()
                                upload_widget.reset()
                                upload_preview.refresh()
                                ul_commit_msg.value = ""
                                registered_sources_view.refresh()
                                if source_refresh_fn:
                                    source_refresh_fn()
                            else:
                                ui.notify(f"エラー: {result['error']}", type="negative")

                        ui.button("Git に登録", on_click=_do_commit, icon="cloud_upload", color="teal")

        # ── 右側: 登録済みソース一覧 ─────────────────────────────
        with ui.column().classes("flex-1 min-w-0"):
            ui.label("登録済みソース").classes("text-subtitle1 text-bold q-mb-sm")
            with ui.row().classes("q-pb-sm gap-3 items-center flex-wrap"):
                ui.input(
                    placeholder="ライブラリ名・ソース名で検索",
                    on_change=_on_filter_change("text"),
                ).props("outlined dense clearable").classes("w-64")
                ui.select(
                    ["全て"] + SYSTEM_TYPES, value="全て", label="システム",
                    on_change=_on_filter_change("system_type"),
                ).props("outlined dense").classes("w-28")
            registered_sources_view()
