import sys
from typing import Callable


COLORS = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
    "reset": "\033[0m",
}


def _supports_color() -> bool:
    """
    Simple check to avoid printing ANSI codes when stdout is not a TTY.
    """
    return sys.stdout.isatty()


def colorize(message: str, color: str) -> str:
    if not _supports_color():
        return message
    code = COLORS.get(color, "")
    reset = COLORS["reset"] if code else ""
    return f"{code}{message}{reset}"


def log(message: str, color: str = "reset"):
    print(colorize(message, color))


def log_info(message: str):
    log(message, "cyan")


def log_success(message: str):
    log(message, "green")


def log_warn(message: str):
    log(message, "yellow")


def log_error(message: str):
    log(message, "red")


def log_debug(message: str):
    log(message, "magenta")
