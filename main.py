import flet as ft
from app.app import ClayBankApp


def main(page: ft.Page) -> None:
    page.title = "ClayBank"
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    # Initialize ClayBank with has_seen_onboarding=True to open directly to the core app shell
    app = ClayBankApp(has_seen_onboarding=True)
    page.add(app)

    # Immediately transition to shell so navigation and views work out-of-the-box
    app.transition_to_shell()
    page.update()


if __name__ == "__main__":
    ft.run(main)
