"""Состояние эмулятора и разрешение путей внутри VFS."""

from dataclasses import dataclass, field
import time

from .vfs import Directory

ROOT_PATH = "/"
CURRENT_COMPONENT = "."
PARENT_COMPONENT = ".."


class CommandError(Exception):
    """Ошибка аргументов или операции над виртуальной файловой системой."""


@dataclass
class ShellState:
    """Корень VFS, текущий каталог и начало работы эмулятора."""

    root: Directory
    cwd: str = ROOT_PATH
    previous_cwd: str = ROOT_PATH
    started: float = field(default_factory=time.monotonic)


def require_directory(node, path):
    """Возвращает каталог или сообщает о попытке прохода через файл."""
    if not isinstance(node, Directory):
        raise CommandError(f"{path}: not a directory")
    return node


def node_at(root, components):
    """Находит узел по уже проверенным компонентам абсолютного пути."""
    node = root
    for name in components:
        node = node.children[name]
    return node


def walk_path(root, components, original):
    """Проходит путь последовательно, проверяя каждый промежуточный узел."""
    node = root
    resolved = []
    for name in components:
        require_directory(node, original)
        if name in ("", CURRENT_COMPONENT):
            continue
        if name == PARENT_COMPONENT:
            if resolved:
                resolved.pop()
            node = node_at(root, resolved)
            continue
        if name not in node.children:
            raise CommandError(f"{original}: no such file or directory")
        node = node.children[name]
        resolved.append(name)
    return ROOT_PATH + ROOT_PATH.join(resolved), node


def resolve_path(state, path):
    """Разрешает абсолютный или относительный POSIX-путь без доступа к ОС."""
    if not path:
        raise CommandError("empty path")
    components = path.split(ROOT_PATH)
    if not path.startswith(ROOT_PATH):
        components = state.cwd.split(ROOT_PATH) + components
    return walk_path(state.root, components, path)
