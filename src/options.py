"""Разбор аргументов встроенных команд без завершения REPL."""

import getopt

from .session import CommandError

EMPTY_COUNT = 0
SINGLE_OPERAND = 1


def parse_options(args, short_options="", long_options=()):
    """Разбирает опции; -- завершает опции, ошибки становятся CommandError."""
    try:
        return getopt.gnu_getopt(args, short_options, list(long_options))
    except getopt.GetoptError as error:
        raise CommandError(str(error)) from error


def require_operands(paths):
    """Требует хотя бы один файловый операнд."""
    if not paths:
        raise CommandError("missing operand")


def require_no_arguments(args):
    """Запрещает аргументы команды, не имеющей параметров."""
    if args:
        raise CommandError("too many arguments")


def single_path(args, default):
    """Возвращает единственный операнд или значение по умолчанию."""
    _, paths = parse_options(args)
    if len(paths) > SINGLE_OPERAND:
        raise CommandError("too many arguments")
    return paths[0] if paths else default


def nonnegative_count(value):
    """Преобразует число строк в целое неотрицательное значение."""
    try:
        number = int(value)
    except ValueError as error:
        raise CommandError(f"invalid line count: {value}") from error
    if number < EMPTY_COUNT:
        raise CommandError(f"invalid line count: {value}")
    return number
