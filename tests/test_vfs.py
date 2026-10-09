"""Проверки XML, структуры папок, текста и двоичных данных."""
import tempfile
import unittest
from pathlib import Path

from src.vfs import Directory, File, VFSError, count_nodes, load_vfs

ROOT = Path(__file__).resolve().parents[1]


class VFSTests(unittest.TestCase):
    def test_minimal(self):
        """Минимальный источник содержит один текстовый файл."""
        root = load_vfs(ROOT / "vfs/minimal.xml")
        self.assertIsInstance(root, Directory)
        self.assertEqual(root.name, "/")
        file = root.children["hello.txt"]
        self.assertIsInstance(file, File)
        self.assertEqual(file.data.decode("utf-8"), "Привет из VFS!")
        self.assertEqual(count_nodes(root), (0, 1))

    def test_multiple_files_and_binary(self):
        """Загрузчик сохраняет текст, пустой файл и двоичные байты."""
        root = load_vfs(ROOT / "vfs/files.xml")
        self.assertEqual(count_nodes(root), (0, 4))
        self.assertEqual(root.children["data.bin"].data, bytes([0, 1, 2, 255]))
        self.assertEqual(root.children["empty.txt"].data, b"")
        self.assertEqual(root.children["notes.txt"].data.decode("utf-8"),
                         "Первая строка\nВторая строка\nТретья строка")

    def test_three_nested_directories(self):
        """Загрузчик сохраняет три уровня вложенных каталогов."""
        root = load_vfs(ROOT / "vfs/nested.xml")
        study = root.children["documents"].children["study"]
        file = study.children["practice"].children["task.txt"]
        self.assertEqual(file.data.decode("utf-8"), "Вариант 13")
        self.assertEqual(count_nodes(root), (3, 2))

    def test_source_is_unchanged_and_nodes_live_in_memory(self):
        """Изменения в памяти не затрагивают XML и другие файлы."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            source = b'<vfs><file name="hello.txt">Hello</file></vfs>'
            path.write_bytes(source)
            root = load_vfs(path)
            root.children["hello.txt"].data = b"Changed in memory"
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            path.unlink()
            self.assertEqual(
                root.children["hello.txt"].data, b"Changed in memory"
            )

    def test_missing_file(self):
        """Отсутствующий источник вызывает VFSError."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(VFSError):
                load_vfs(Path(directory) / "missing.xml")

    def test_invalid_formats(self):
        """Неверная структура XML и base64 вызывают VFSError."""
        examples = [
            '<vfs>', '<root/>', '<vfs><unknown/></vfs>',
            '<vfs><file/></vfs>', '<vfs><directory name="../docs"/></vfs>',
            '<vfs><file name="x"/><directory name="x"/></vfs>',
            '<vfs><file name="x" encoding="hex">00</file></vfs>',
            '<vfs><file name="x" encoding="base64">!!!</file></vfs>',
            '<vfs><file name="x"><file name="y"/></file></vfs>',
            '<vfs>unexpected text</vfs>',
            '<vfs extra="x"/>', '<vfs><file name="."/></vfs>',
            '<vfs><file name=".."/></vfs>',
            '<vfs><file name="x" extra="y"/></vfs>',
            '<vfs><directory name="x" encoding="text"/></vfs>',
            '<vfs><file name="x"/>unexpected tail</vfs>',
            '<vfs><directory name="x">unexpected text</directory></vfs>',
            '<vfs><file name="x" encoding="base64">Я</file></vfs>',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            for example in examples:
                with self.subTest(xml=example):
                    path.write_text(example, encoding="utf-8")
                    with self.assertRaises(VFSError):
                        load_vfs(path)

    def test_empty_root_and_base64_whitespace(self):
        """Пустой корень и переносы строк base64 допустимы."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            path.write_text('<vfs/>', encoding="utf-8")
            self.assertEqual(count_nodes(load_vfs(path)), (0, 0))
            path.write_text(
                '<vfs><file name="x" encoding="base64">'
                ' AAEC\n/w== </file></vfs>', encoding="utf-8"
            )
            self.assertEqual(
                load_vfs(path).children["x"].data, bytes([0, 1, 2, 255])
            )


if __name__ == "__main__":
    unittest.main()
