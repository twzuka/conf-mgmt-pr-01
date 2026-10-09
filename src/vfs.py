"""Загрузка виртуальной файловой системы из XML в память."""

import base64
import binascii
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET


@dataclass
class File:
    """Виртуальный файл: имя и содержимое в байтах."""

    name: str
    data: bytes


@dataclass
class Directory:
    """Виртуальная папка: имя и словарь вложенных элементов."""

    name: str
    children: dict = field(default_factory=dict)


class VFSError(Exception):
    """Ошибка чтения или формата VFS."""


def validate_text(text):
    """Запрещает текст вне элемента file, кроме пробельных символов."""
    if text and text.strip():
        raise VFSError("Текст должен находиться внутри элемента file")


def validate_name(name):
    """Проверяет непустое имя без разделителей и специальных компонентов."""
    if not name.strip() or name in (".", ".."):
        raise VFSError(f"Недопустимое имя: {name!r}")
    if "/" in name or "\\" in name:
        raise VFSError(f"Недопустимое имя: {name!r}")


def validate_child(element, directory):
    """Проверяет тег, имя, атрибуты и уникальность вложенного элемента."""
    if element.tag not in ("directory", "file"):
        raise VFSError(f"Неизвестный элемент: {element.tag}")
    name = element.get("name", "")
    validate_name(name)
    if name in directory.children:
        raise VFSError(f"Повторяющееся имя: {name}")
    allowed = {"name"}
    if element.tag == "file":
        allowed.add("encoding")
    if set(element.attrib) - allowed:
        raise VFSError(f"Неизвестный атрибут у {name}")
    validate_text(element.tail)
    return name


def decode_base64(text, name):
    """Декодирует base64 с пробельными символами или сообщает об ошибке."""
    try:
        return base64.b64decode("".join(text.split()), validate=True)
    except (binascii.Error, ValueError) as error:
        raise VFSError(f"Неверный base64 в файле {name}") from error


def read_file(element, name):
    """Читает текстовый или двоичный файл без вложенных XML-элементов."""
    if len(element):
        raise VFSError(f"Файл {name} не может содержать элементы XML")
    encoding = element.get("encoding", "text")
    text = element.text or ""
    if encoding == "text":
        data = text.encode("utf-8")
    elif encoding == "base64":
        data = decode_base64(text, name)
    else:
        raise VFSError(f"Неизвестная кодировка: {encoding}")
    return File(name, data)


def read_directory(element, name):
    """Рекурсивно строит дерево каталогов и файлов в памяти."""
    directory = Directory(name)
    validate_text(element.text)
    for child in element:
        child_name = validate_child(child, directory)
        if child.tag == "directory":
            node = read_directory(child, child_name)
        else:
            node = read_file(child, child_name)
        directory.children[child_name] = node
    return directory


def load_vfs(path):
    """Читает XML, возвращает корень, не изменяя исходный файл."""
    try:
        element = ET.parse(path).getroot()
    except FileNotFoundError as error:
        raise VFSError(f"Файл не найден: {path}") from error
    except (ET.ParseError, UnicodeError, ValueError) as error:
        raise VFSError(f"Неверный формат XML: {error}") from error
    except OSError as error:
        raise VFSError(f"Не удалось прочитать VFS: {error}") from error
    if element.tag != "vfs" or element.attrib:
        raise VFSError("Корневой элемент должен быть <vfs> без атрибутов")
    try:
        return read_directory(element, "/")
    except RecursionError as error:
        raise VFSError("Слишком большая вложенность папок") from error


def count_nodes(directory):
    """Считает папки и файлы без учёта корневой папки."""
    directories = 0
    files = 0
    for node in directory.children.values():
        if isinstance(node, Directory):
            nested_dirs, nested_files = count_nodes(node)
            directories += 1 + nested_dirs
            files += nested_files
        else:
            files += 1
    return directories, files
