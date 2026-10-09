"""Проверки chown, touch, временных меток и сохранности источника VFS."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import main as shell
from src.session import ShellState
from src.vfs import Directory, File, load_vfs
from test_main import call_and_capture

TEST_TIME = 1234567890.0


class MutationTests(unittest.TestCase):
    """Изменения виртуальных файлов и каталогов без операций над ОС."""

    def setUp(self):
        """Создаёт каталог и файл с фиксированным содержимым и метками."""
        self.file = File("text", b"original", owner="alice", group="staff",
                         accessed=1.0, modified=2.0)
        self.docs = Directory("docs", {"text": self.file}, owner="alice")
        self.state = ShellState(Directory("/", {"docs": self.docs}))

    def run_line(self, line):
        """Выполняет строку и перехватывает вывод команд."""
        return call_and_capture(shell.execute_line, line, self.state)

    def test_chown_owner_and_group(self):
        """chown меняет владельца и группу, не меняя данные и метки."""
        self.run_line("chown bob docs/text")
        self.assertEqual(self.file.owner, "bob")
        self.assertEqual(self.file.group, "staff")
        self.run_line("chown carol:students docs/text")
        self.assertEqual((self.file.owner, self.file.group),
                         ("carol", "students"))
        self.assertEqual(self.file.data, b"original")
        self.assertEqual((self.file.accessed, self.file.modified), (1.0, 2.0))

    def test_chown_directories_root_and_multiple_operands(self):
        """chown обрабатывает каталоги, корень и несколько путей."""
        self.run_line("chown 1000:2000 / docs docs/text")
        for node in (self.state.root, self.docs, self.file):
            self.assertEqual((node.owner, node.group), ("1000", "2000"))
        _, output = self.run_line("ls -l docs/text")
        self.assertIn("1000 2000", output)

    def test_chown_directory_is_not_recursive(self):
        """Изменение владельца каталога не меняет его дочерние файлы."""
        self.run_line("chown bob docs")
        self.assertEqual(self.docs.owner, "bob")
        self.assertEqual(self.file.owner, "alice")

    def test_chown_errors_do_not_stop_later_paths(self):
        """Ошибка одного пути не мешает изменению остальных операндов."""
        result, output = self.run_line("chown bob missing docs/text")
        self.assertTrue(result)
        self.assertIn("no such file or directory", output)
        self.assertEqual(self.file.owner, "bob")

    def test_touch_creates_empty_files_and_updates_existing(self):
        """touch создаёт пустой файл и сохраняет содержимое существующего."""
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch new docs/text")
        node = self.state.root.children["new"]
        self.assertIsInstance(node, File)
        self.assertEqual(node.data, b"")
        self.assertEqual((node.accessed, node.modified), (TEST_TIME, TEST_TIME))
        self.assertEqual(self.file.data, b"original")
        self.assertEqual((self.file.accessed, self.file.modified),
                         (TEST_TIME, TEST_TIME))
        _, output = self.run_line("ls")
        self.assertIn("new", output.splitlines())

    def test_touch_access_and_modified_modes(self):
        """-a меняет только доступ, -m только модификацию, -am обе метки."""
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch -a docs/text")
        self.assertEqual((self.file.accessed, self.file.modified),
                         (TEST_TIME, 2.0))
        self.file.accessed = 1.0
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch -m docs/text")
        self.assertEqual((self.file.accessed, self.file.modified),
                         (1.0, TEST_TIME))
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch -am docs/text")
        self.assertEqual((self.file.accessed, self.file.modified),
                         (TEST_TIME, TEST_TIME))

    def test_touch_no_create_and_option_terminator(self):
        """-c не создаёт файл, -- позволяет использовать имя с дефисом."""
        _, output = self.run_line("touch -c missing")
        self.assertEqual(output, "")
        self.assertNotIn("missing", self.state.root.children)
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch -c docs/text")
        self.assertEqual(self.file.modified, TEST_TIME)
        self.run_line("touch -- -file")
        self.run_line("chown bob -- -file")
        self.assertEqual(self.state.root.children["-file"].owner, "bob")

    def test_touch_relative_paths_and_directory_timestamps(self):
        """touch поддерживает относительные пути и метки каталогов."""
        self.run_line("cd docs")
        with mock.patch("src.mutations.time.time", return_value=TEST_TIME):
            self.run_line("touch child . .. /docs/")
        self.assertEqual(self.docs.children["child"].data, b"")
        self.assertEqual(self.docs.modified, TEST_TIME)
        self.assertEqual(self.state.root.modified, TEST_TIME)

    def test_touch_errors_do_not_stop_later_operands(self):
        """touch не создаёт родительские каталоги и продолжает после ошибки."""
        result, output = self.run_line("touch missing/child docs/text/child ok")
        self.assertTrue(result)
        self.assertIn("no such file or directory", output)
        self.assertIn("not a directory", output)
        self.assertIn("ok", self.state.root.children)
        self.assertNotIn("missing", self.state.root.children)

    def test_invalid_arguments_preserve_file(self):
        """Ошибочные владельцы и опции не меняют существующий файл."""
        lines = (
            "chown", "chown bob", "chown bad:name:group docs/text",
            "chown :staff docs/text", "chown bob: docs/text",
            "chown -R bob docs/text", "touch", "touch -z docs/text",
            "touch docs/text/", "touch docs/text/..",
        )
        for line in lines:
            with self.subTest(line=line):
                result, output = self.run_line(line)
                self.assertTrue(result)
                self.assertTrue(output.startswith(line.split()[0] + ":"))
                self.assertEqual(self.file.owner, "alice")
                self.assertEqual(self.file.data, b"original")
                self.assertEqual(self.file.modified, 2.0)


class PersistenceTests(unittest.TestCase):
    """Проверяет отсутствие записи в источник и сброс после перезапуска."""

    def test_mutations_live_only_in_memory(self):
        """Файлы и владельцы изменяются в памяти, исходный XML не меняется."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vfs.xml"
            source = b'<vfs><file name="hello">Hello</file></vfs>'
            path.write_bytes(source)
            state = ShellState(load_vfs(path))
            call_and_capture(shell.execute_line, "touch new hello", state)
            call_and_capture(shell.execute_line, "chown bob hello new", state)
            self.assertEqual(state.root.children["hello"].owner, "bob")
            self.assertIn("new", state.root.children)
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            reloaded = load_vfs(path)
            self.assertNotIn("new", reloaded.children)
            with mock.patch("src.vfs.getpass.getuser", return_value="alice"):
                self.assertEqual(load_vfs(path).children["hello"].owner,
                                 "alice")
            path.unlink()
            call_and_capture(shell.execute_line, "touch after_delete", state)
            self.assertIn("after_delete", state.root.children)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_startup_mutations_are_visible_in_repl(self):
        """Изменения сценария видны интерактивным командам этого же сеанса."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            vfs = folder / "vfs.xml"
            source = b'<vfs><directory name="docs"/></vfs>'
            vfs.write_bytes(source)
            script = folder / "startup.txt"
            script.write_text(
                "cd docs\ntouch new\nchown bob new\n", encoding="utf-8"
            )
            with mock.patch("builtins.input", side_effect=["ls -l", "exit"]):
                code, output = call_and_capture(shell.main, [
                    "--vfs-path", str(vfs), "--script", str(script)
                ])
            self.assertEqual(code, 0)
            self.assertIn("bob users 0", output)
            self.assertTrue(output.endswith(" new\n"))
            self.assertEqual(vfs.read_bytes(), source)
            self.assertEqual(set(folder.iterdir()), {vfs, script})

    def test_default_owner_fallback(self):
        """Начальный владелец получает запасное имя при ошибке ОС."""
        with mock.patch("src.vfs.getpass.getuser", side_effect=OSError):
            self.assertEqual(File("x", b"").owner, "user")


if __name__ == "__main__":
    unittest.main()
