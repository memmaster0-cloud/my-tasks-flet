import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import flet as ft


# Supabase config generated during GitHub Actions build
try:
    from app_config import SUPABASE_URL as CONFIG_URL
    from app_config import SUPABASE_KEY as CONFIG_KEY
except ImportError:
    CONFIG_URL = None
    CONFIG_KEY = None


TABLE_NAME = "tasks"


def get_config():
    url = os.getenv("SUPABASE_URL") or CONFIG_URL
    key = os.getenv("SUPABASE_KEY") or CONFIG_KEY

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are not configured."
        )

    return url.rstrip("/"), key


def supabase_request(
    method,
    path,
    params=None,
    body=None,
):
    """
    Прямой запрос к Supabase REST API.
    Используется urllib, без supabase-py и httpx.
    """

    url, key = get_config()

    request_url = f"{url}/rest/v1/{path}"

    if params:
        request_url += "?" + urlencode(params)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "my-tasks-flet/1.0",
    }

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    request = Request(
        request_url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=20) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")

            if not raw:
                return status_code, None

            try:
                return status_code, json.loads(raw)
            except json.JSONDecodeError:
                return status_code, raw

    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")

        raise RuntimeError(
            f"Supabase HTTP {exc.code}: {raw}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Ошибка сети Supabase: {exc}"
        ) from exc


def get_tasks():
    status_code, data = supabase_request(
        "GET",
        TABLE_NAME,
        params={
            "select": "id,title,done,created_at",
            "order": "created_at.desc",
        },
    )

    if status_code != 200:
        raise RuntimeError(
            f"Ошибка загрузки задач: HTTP {status_code}"
        )

    if data is None:
        return []

    if not isinstance(data, list):
        raise RuntimeError(
            "Supabase вернул неожиданный формат данных: "
            f"{type(data).__name__}: {data}"
        )

    return data


def create_task(title):
    status_code, data = supabase_request(
        "POST",
        TABLE_NAME,
        params={
            "select": "id,title,done,created_at",
        },
        body={
            "title": title,
            "done": False,
        },
    )

    if status_code not in (200, 201):
        raise RuntimeError(
            f"Ошибка добавления задачи: HTTP {status_code}"
        )

    return data


def update_task(task_id, done):
    status_code, data = supabase_request(
        "PATCH",
        TABLE_NAME,
        params={
            "id": f"eq.{task_id}",
        },
        body={
            "done": done,
        },
    )

    if status_code not in (200, 204):
        raise RuntimeError(
            f"Ошибка обновления задачи: HTTP {status_code}"
        )

    return data


def delete_task(task_id):
    status_code, data = supabase_request(
        "DELETE",
        TABLE_NAME,
        params={
            "id": f"eq.{task_id}",
        },
    )

    if status_code not in (200, 204):
        raise RuntimeError(
            f"Ошибка удаления задачи: HTTP {status_code}"
        )

    return data


def main(page: ft.Page):
    page.title = "Мои задачи"
    page.padding = 16
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    title_field = ft.TextField(
        label="Название задачи",
        hint_text="Например: подготовить отчёт",
        width=350,
    )

    tasks_list = ft.ListView(
        expand=True,
        spacing=8,
        auto_scroll=False,
    )

    status = ft.Text(
        "Готово",
        color=ft.Colors.GREY_700,
    )

    def show_error(message):
        status.value = f"Ошибка: {message}"
        status.color = ft.Colors.RED_700
        page.update()

    def show_ok(message):
        status.value = message
        status.color = ft.Colors.GREEN_700
        page.update()

    def load_tasks():
        try:
            tasks = get_tasks()

            tasks_list.controls.clear()

            for task in tasks:

                if not isinstance(task, dict):
                    raise RuntimeError(
                        "Supabase вернул задачу не как объект: "
                        f"{type(task).__name__}"
                    )

                task_id = task["id"]
                task_title = task["title"]
                done = bool(task["done"])

                def toggle_task(
                    e,
                    item_id=task_id,
                    old_value=done,
                ):
                    try:
                        update_task(
                            item_id,
                            not old_value,
                        )

                        load_tasks()
                        show_ok("Статус задачи изменён")

                    except Exception as exc:
                        show_error(str(exc))

                def remove_task(
                    e,
                    item_id=task_id,
                ):
                    try:
                        delete_task(item_id)

                        load_tasks()
                        show_ok("Задача удалена")

                    except Exception as exc:
                        show_error(str(exc))

                task_text = ft.Text(
                    task_title,
                    expand=True,
                    size=16,
                    weight=(
                        ft.FontWeight.NORMAL
                        if done
                        else ft.FontWeight.BOLD
                    ),
                    style=(
                        ft.TextStyle(
                            decoration=ft.TextDecoration.LINE_THROUGH
                        )
                        if done
                        else None
                    ),
                )

                task_card = ft.Card(
                    content=ft.Container(
                        padding=10,
                        content=ft.Row(
                            [
                                ft.Checkbox(
                                    value=done,
                                    on_change=toggle_task,
                                ),

                                task_text,

                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    tooltip="Удалить",
                                    on_click=remove_task,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER
                            ),
                        ),
                    ),
                )

                tasks_list.controls.append(task_card)

            page.update()

        except Exception as exc:
            show_error(str(exc))

    def add_task(e):
        title = (title_field.value or "").strip()

        if not title:
            show_error("Введите название задачи")
            return

        try:
            create_task(title)

            title_field.value = ""

            load_tasks()
            show_ok("Задача добавлена")

        except Exception as exc:
            show_error(str(exc))

    def refresh(e):
        load_tasks()
        show_ok("Список обновлён")

    title_field.on_submit = add_task

    page.add(
        ft.Text(
            "Мои задачи",
            size=28,
            weight=ft.FontWeight.BOLD,
        ),

        ft.Column(
            [
                title_field,

                ft.FilledButton(
                    "Добавить",
                    icon=ft.Icons.ADD,
                    on_click=add_task,
                    width=160,
                ),
            ],
            spacing=10,
        ),

        ft.Row(
            [
                ft.OutlinedButton(
                    "Обновить",
                    icon=ft.Icons.REFRESH,
                    on_click=refresh,
                ),

                status,
            ],
            wrap=True,
            spacing=10,
        ),

        ft.Divider(),

        ft.Container(
            content=tasks_list,
            expand=True,
        ),
    )

    load_tasks()


if __name__ == "__main__":
    ft.run(main)