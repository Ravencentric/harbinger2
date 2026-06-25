from pytest import CaptureFixture, MonkeyPatch

from harbinger.cli import console
from harbinger.cli.console import Style


def test_style() -> None:
    assert console.Style.RESET.marker == "[/]"
    assert console.Style.RESET.to_ansi() == "\033[0m"


def test_stdout_stderr(capsys: CaptureFixture[str]) -> None:
    console.stdout("Hello from stdout")
    console.stderr("Hello from stderr")
    out, err = capsys.readouterr()
    assert out == "Hello from stdout\n"
    assert err == "Hello from stderr\n"


def test_render(monkeypatch: MonkeyPatch) -> None:
    text = "[cyan]cyan[/] [red]red[/] [dim]dim[/] normal"
    plain = "cyan red dim normal"
    rendered = (
        f"{Style.CYAN}cyan{Style.RESET} "
        f"{Style.RED}red{Style.RESET} "
        f"{Style.DIM}dim{Style.RESET} "
        "normal"
    )

    monkeypatch.setattr(console, "can_colorize", lambda: True)
    assert console.can_colorize() is True
    assert console.render(text) == rendered

    monkeypatch.setattr(console, "can_colorize", lambda: False)
    assert console.can_colorize() is False
    assert console.render(text) == plain
