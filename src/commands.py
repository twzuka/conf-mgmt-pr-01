"""Основные команды UNIX-подобной оболочки над VFS в памяти."""

from datetime import datetime, timezone
import time

from .options import (
    EMPTY_COUNT,
    SINGLE_OPERAND,
    nonnegative_count,
    parse_options,
    require_no_arguments,
    require_operands,
    single_path,
)
from .session import CommandError, require_directory, resolve_path
from .vfs import Directory

DEFAULT_HEAD_LINES = 10
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
PREVIOUS_DIRECTORY = "-"


def list_entries(node, path, show_all):
    """Возвращает отсортированные элементы каталога или сам файл."""
    if not isinstance(node, Directory):
        return [(path, node)]
    entries = sorted(node.children.items())
    if show_all:
        return entries
    return [(name, child) for name, child in entries
            if not name.startswith(".")]


def format_entry(name, node, long_format):
    """Форматирует имя либо тип, владельца, группу, размер и время UTC."""
    if not long_format:
        return name
    kind = "d" if isinstance(node, Directory) else "-"
    size = 0 if isinstance(node, Directory) else len(node.data)
    modified = datetime.fromtimestamp(node.modified, timezone.utc)
    stamp = modified.isoformat(timespec="seconds")
    return f"{kind} {node.owner} {node.group} {size} {stamp} {name}"


def command_ls(state, args):
    """Выводит каталог или файл; поддерживает -a, -l и несколько путей."""
    options, paths = parse_options(args, "al")
    flags = {option for option, _ in options}
    paths = paths or [state.cwd]
    errors = []
    for path in paths:
        try:
            _, node = resolve_path(state, path)
            if len(paths) > SINGLE_OPERAND:
                print(f"{path}:")
            for name, child in list_entries(node, path, "-a" in flags):
                print(format_entry(name, child, "-l" in flags))
        except CommandError as error:
            errors.append(str(error))
    if errors:
        raise CommandError("; ".join(errors))


def command_cd(state, args):
    """Меняет каталог; без пути переходит в /, cd - возвращает предыдущий."""
    if args == [PREVIOUS_DIRECTORY]:
        path = state.previous_cwd
    else:
        path = single_path(args, "/")
    canonical, node = resolve_path(state, path)
    require_directory(node, path)
    state.previous_cwd, state.cwd = state.cwd, canonical
    if args == [PREVIOUS_DIRECTORY]:
        print(state.cwd)


def read_text(state, path):
    """Возвращает UTF-8-текст файла; каталоги и двоичные данные запрещены."""
    _, node = resolve_path(state, path)
    if isinstance(node, Directory):
        raise CommandError(f"{path}: is a directory")
    try:
        return node.data.decode("utf-8")
    except UnicodeError as error:
        raise CommandError(f"{path}: not a UTF-8 text file") from error


def first_lines(text, count):
    """Возвращает первые строки, считая разделителем только символ LF."""
    if count == EMPTY_COUNT:
        return ""
    parts = text.split("\n")
    result = "\n".join(parts[:count])
    if len(parts) > count:
        result += "\n"
    return result


def output_files(state, paths, line_count=None):
    """Выводит доступные текстовые файлы, сохраняя сведения об ошибках."""
    errors = []
    for path in paths:
        try:
            text = read_text(state, path)
            if line_count is not None:
                text = first_lines(text, line_count)
                if len(paths) > SINGLE_OPERAND:
                    print(f"==> {path} <==")
            print(text, end="")
        except CommandError as error:
            errors.append(str(error))
    if errors:
        raise CommandError("; ".join(errors))


def command_cat(state, args):
    """Выводит содержимое одного или нескольких UTF-8-файлов."""
    _, paths = parse_options(args)
    require_operands(paths)
    output_files(state, paths)


def command_head(state, args):
    """Выводит первые 10 строк или число строк из -n/--lines."""
    options, paths = parse_options(args, "n:", ("lines=",))
    require_operands(paths)
    count = DEFAULT_HEAD_LINES
    for _, value in options:
        count = nonnegative_count(value)
    output_files(state, paths, count)


def command_uptime(state, args):
    """Выводит время работы эмулируемой ОС с момента запуска приложения."""
    require_no_arguments(args)
    elapsed = int(time.monotonic() - state.started)
    minutes, seconds = divmod(elapsed, SECONDS_PER_MINUTE)
    hours, minutes = divmod(minutes, MINUTES_PER_HOUR)
    print(f"up {hours:02}:{minutes:02}:{seconds:02}")


COMMANDS = {
    "ls": command_ls,
    "cd": command_cd,
    "uptime": command_uptime,
    "cat": command_cat,
    "head": command_head,
}
