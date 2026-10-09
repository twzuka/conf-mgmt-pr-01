"""Команды этапа 5: изменение владельца и временных меток только в памяти."""

import re
import time

from .options import SINGLE_OPERAND, parse_options, require_operands
from .session import CommandError, require_directory, resolve_path
from .vfs import File, VFSError, validate_name

IDENTIFIER_PATTERN = r"[A-Za-z_][A-Za-z0-9_.-]*[$]?|[0-9]+"


def parse_ownership(value):
    """Разбирает OWNER или OWNER:GROUP без обращения к пользователям ОС."""
    owner, separator, group = value.partition(":")
    if re.fullmatch(IDENTIFIER_PATTERN, owner) is None:
        raise CommandError(f"invalid owner: {value}")
    if separator and re.fullmatch(IDENTIFIER_PATTERN, group) is None:
        raise CommandError(f"invalid group: {value}")
    return owner, group if separator else None


def apply_ownership(state, paths, owner, group):
    """Меняет владельца узлов, продолжая обработку после ошибочного пути."""
    errors = []
    for path in paths:
        try:
            _, node = resolve_path(state, path)
            node.owner = owner
            if group is not None:
                node.group = group
        except CommandError as error:
            errors.append(str(error))
    if errors:
        raise CommandError("; ".join(errors))


def command_chown(state, args):
    """Меняет владельца и необязательную группу файлов или каталогов."""
    _, operands = parse_options(args)
    if len(operands) <= SINGLE_OPERAND:
        raise CommandError("usage: chown OWNER[:GROUP] PATH ...")
    owner, group = parse_ownership(operands[0])
    apply_ownership(state, operands[1:], owner, group)


def find_or_create_file(state, path, no_create):
    """Находит узел или создаёт пустой файл в существующем каталоге."""
    parent_path, separator, name = path.rpartition("/")
    if name in ("", ".", ".."):
        _, node = resolve_path(state, path)
        return node
    try:
        validate_name(name)
    except VFSError as error:
        raise CommandError(str(error)) from error
    if not separator:
        parent_path = state.cwd
    elif not parent_path:
        parent_path = "/"
    _, parent = resolve_path(state, parent_path)
    require_directory(parent, parent_path)
    if name in parent.children:
        return parent.children[name]
    if no_create:
        return None
    node = File(name, b"")
    parent.children[name] = node
    return node


def update_timestamps(node, timestamp, access_only, modified_only):
    """Обновляет время доступа, модификации или обе метки без потери данных."""
    if not modified_only or access_only:
        node.accessed = timestamp
    if not access_only or modified_only:
        node.modified = timestamp


def touch_paths(state, paths, flags):
    """Обрабатывает пути touch в памяти, продолжая после ошибок операнда."""
    errors = []
    timestamp = time.time()
    for path in paths:
        try:
            node = find_or_create_file(state, path, "-c" in flags)
            if node is not None:
                update_timestamps(node, timestamp,
                                  "-a" in flags, "-m" in flags)
        except CommandError as error:
            errors.append(str(error))
    if errors:
        raise CommandError("; ".join(errors))


def command_touch(state, args):
    """Создаёт файлы и обновляет метки: -a, -m, -c."""
    options, paths = parse_options(args, "amc")
    require_operands(paths)
    flags = {option for option, _ in options}
    touch_paths(state, paths, flags)


COMMANDS = {
    "chown": command_chown,
    "touch": command_touch,
}
