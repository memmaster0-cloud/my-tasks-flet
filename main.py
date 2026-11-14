import os
import flet as ft
from supabase import create_client, Client


# Supabase config generated during GitHub Actions build
try:
    from app_config import SUPABASE_URL as CONFIG_URL
    from app_config import SUPABASE_KEY as CONFIG_KEY
except ImportError:
    CONFIG_URL = None
    CONFIG_KEY = None


TABLE_NAME = "tasks"


def get_config() -> tuple[str, str]:
    """Get Supabase credentials from environment or bundled app config."""

    url = os.getenv("SUPABASE_URL") or CONFIG_URL
    key = os.getenv("SUPABASE_KEY") or CONFIG_KEY

    if url and key:
        return url, key

    raise RuntimeError(
        "Supabase credentials are not configured. "
        "Set SUPABASE_URL and SUPABASE_KEY."
    )


def create_supabase_client() -> Client:
    url, key = get_config()
    return create_client(url, key)


def main(page: ft.Page):
    page.title = "Мои задачи"
    page.padding = 16
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO

    try:
        supabase = create_supabase_client()
    except Exception as exc:
        page.add(
            ft.Text(
                "Ошибка подключения к Supabase",
                size=22,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(str(exc), selectable=True),
        )
        return

    title_field = ft.TextField(
        label="Название задачи",
        hint_text="Например: подготовить отчёт",
        expand=True,
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

    def show_error(message: str):
        status.value = f"Ошибка: {message}"
        status.color = ft.Colors.RED_700
        page.update()

    def show_ok(message: str):
        status.value = message
        status.color = ft.Colors.GREEN_700
        page.update()

    def load_tasks():
        try:
            response = (
                supabase.table(TABLE_NAME)
                .select("id,title,done,created_at")
                .order("created_at", desc=True)
                .execute()
            )

            tasks_list.controls.clear()

            for task in response.data or []:
                task_id = task["id"]
                done = bool(task["done"])

                def toggle_task(
                    e,
                    item_id=task_id,
                    old_value=done,
                ):
                    try:
                        supabase.table(TABLE_NAME).update(
                            {"done": not old_value}
                        ).eq(
                            "id", item_id
                        ).execute()

                        load_tasks()
                        show_ok("Статус задачи изменён")

                    except Exception as exc:
                        show_error(str(exc))

                def delete_task(e, item_id=task_id):
                    try:
                        supabase.table(TABLE_NAME).delete().eq(
                            "id", item_id
                        ).execute()

                        load_tasks()
                        show_ok("Задача удалена")

                    except Exception as exc:
                        show_error(str(exc))

                tasks_list.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=10,
                            content=ft.Row(
                                [
                                    ft.Checkbox(
                                        value=done,
                                        on_change=toggle_task,
                                    ),
                                    ft.Text(
                                        task["title"],
                                        expand=True,
                                        size=16,
                                        weight=(
                                            ft.FontWeight.BOLD
                                            if not done
                                            else ft.FontWeight.NORMAL
                                        ),
                                        style=(
                                            ft.TextStyle(
                                                decoration=(
                                                    ft.TextDecoration.LINE_THROUGH
                                                )
                                            )
                                            if done
                                            else None
                                        ),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        tooltip="Удалить",
                                        on_click=delete_task,
                                    ),
                                ],
                                alignment=(
                                    ft.MainAxisAlignment.SPACE_BETWEEN
                                ),
                            ),
                        )
                    )
                )

            page.update()

        except Exception as exc:
            show_error(str(exc))

    def add_task(e):
        title = (title_field.value or "").strip()

        if not title:
            show_error("Введите название задачи")
            return

        try:
            supabase.table(TABLE_NAME).insert(
                {
                    "title": title,
                    "done": False,
                }
            ).execute()

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
        ft.Row(
            [
                title_field,
                ft.FilledButton(
                    "Добавить",
                    icon=ft.Icons.ADD,
                    on_click=add_task,
                ),
            ]
        ),
        ft.Row(
            [
                ft.OutlinedButton(
                    "Обновить",
                    icon=ft.Icons.REFRESH,
                    on_click=refresh,
                ),
                status,
            ]
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