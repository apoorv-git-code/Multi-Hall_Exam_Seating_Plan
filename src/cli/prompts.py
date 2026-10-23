"""Input prompts for the interactive menu.

Every function takes ``input_fn`` and ``output_fn`` so tests can feed scripted
answers. They re-ask until the answer is valid. If input ends (end of file or
Ctrl+C) they raise ``UserQuit`` so a script or a closed terminal never loops
forever.

This module contains no algorithm logic.
"""

from __future__ import annotations

from typing import Callable

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


class UserQuit(Exception):
    """Raised when input ends or the user interrupts a prompt."""


def read_line(prompt: str, input_fn: InputFn = input) -> str:
    """Read one stripped line, turning end of input into ``UserQuit``.

    Time: O(len(line)). Space: O(len(line)).
    """
    try:
        return input_fn(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        raise UserQuit from None


def ask_text(
    prompt: str,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    default: str | None = None,
    allow_empty: bool = False,
) -> str:
    """Ask for free text. An empty answer returns ``default`` when one is given.

    Without a default, an empty answer is rejected unless ``allow_empty`` is True.
    """
    suffix = f" [{default}]" if default is not None else ""
    while True:
        answer = read_line(f"{prompt}{suffix}: ", input_fn)
        if answer == "" and default is not None:
            return default
        if answer != "" or allow_empty:
            return answer
        output_fn("Please enter a value.")


def ask_int(
    prompt: str,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    minimum: int = 1,
    maximum: int = 1000000,
    default: int | None = None,
) -> int:
    """Ask for an integer between ``minimum`` and ``maximum`` (inclusive)."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        answer = read_line(f"{prompt} ({minimum}-{maximum}){suffix}: ", input_fn)
        if answer == "" and default is not None:
            return default
        try:
            value = int(answer)
        except ValueError:
            output_fn(f"'{answer}' is not a whole number.")
            continue
        if value < minimum or value > maximum:
            output_fn(f"Please enter a number from {minimum} to {maximum}.")
            continue
        return value


def ask_choice(
    prompt: str,
    options: list[str],
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    default: str | None = None,
) -> str:
    """Ask the user to pick one of ``options`` by name or by 1-based number.

    Names are matched case-insensitively. Returns the option as written in
    ``options``.
    """
    listing = ", ".join(f"{i + 1}) {name}" for i, name in enumerate(options))
    suffix = f" [{default}]" if default is not None else ""
    while True:
        answer = read_line(f"{prompt} ({listing}){suffix}: ", input_fn)
        if answer == "" and default is not None:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        for name in options:
            if name.lower() == answer.lower():
                return name
        output_fn(f"Please choose one of: {', '.join(options)}.")


def ask_yes_no(
    prompt: str,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    default: bool = True,
) -> bool:
    """Ask a yes/no question. An empty answer returns ``default``."""
    hint = "Y/n" if default else "y/N"
    while True:
        answer = read_line(f"{prompt} [{hint}]: ", input_fn).lower()
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        output_fn("Please answer y or n.")
