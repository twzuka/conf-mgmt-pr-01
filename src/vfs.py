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


def read_directory(element, name):
    """Рекурсивно читает содержимое папки."""
    directory = Directory(name)
    if element.text and element.text.strip():
        raise VFSError("Текст должен находиться внутри элемента file")
    for child in element:
        if child.tag not in ("directory", "file"):
            raise VFSError(f"Неизвестный элемент: {child.tag}")
        child_name = child.get("name", "")
        if (not child_name.strip() or child_name in (".", "..")
                or "/" in child_name or "\\" in child_name):
            raise VFSError(f"Недопустимое имя: {child_name!r}")
        if child_name in directory.children:
            raise VFSError(f"Повторяющееся имя: {child_name}")
        allowed = {"name"} if child.tag == "directory" else {"name", "encoding"}
        if set(child.attrib) - allowed:
            raise VFSError(f"Неизвестный атрибут у {child_name}")
        if child.tail and child.tail.strip():
            raise VFSError("Текст должен находиться внутри элемента file")
        if child.tag == "directory":
            node = read_directory(child, child_name)
        else:
            if len(child):
                raise VFSError(f"Файл {child_name} не может содержать элементы XML")
            encoding = child.get("encoding", "text")
            text = child.text or ""
            if encoding == "text":
                data = text.encode("utf-8")
            elif encoding == "base64":
                try:
                    data = base64.b64decode("".join(text.split()), validate=True)
                except (binascii.Error, ValueError) as error:
                    raise VFSError(f"Неверный base64 в файле {child_name}") from error
            else:
                raise VFSError(f"Неизвестная кодировка: {encoding}")
            node = File(child_name, data)
        directory.children[child_name] = node
    return directory


def load_vfs(path):
    """Читает XML, возвращает корневую папку. Исходный файл не изменяется."""
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
