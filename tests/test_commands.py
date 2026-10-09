"""Проверки команд этапа 4, виртуальных путей и общего состояния сеанса."""

import os
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from src import main as shell
from src.commands import read_text
from src.session import CommandError, ShellState, resolve_path
from src.vfs import Directory, File
from test_main import call_and_capture


class CommandTests(unittest.TestCase):
    """Проверка наблюдаемого поведения встроенных команд."""

    def setUp(self):
        """Создаёт VFS с вложенными, пустыми и двоичными файлами."""
        lines = "".join(f"line {number}\n" for number in range(1, 13))
        leaf = Directory("leaf", {"text": File("text", b"last\n")})
        docs = Directory("docs", {"leaf": leaf})
        self.root = Directory("/", {
            "docs": docs,
            "empty": Directory("empty"),
            "alpha": File("alpha", b"first\nsecond\nthird"),
            "long": File("long", lines.encode()),
            "blank": File("blank", b""),
            "binary": File("binary", b"\xff\x00"),
            ".hidden": File(".hidden", b"secret"),
            "-file": File("-file", b"dash"),
        })
        self.state = ShellState(self.root)

    def run_line(self, line):
        """Выполняет команду и возвращает признак продолжения и вывод."""
        return call_and_capture(shell.execute_line, line, self.state)

    def test_ls_default_and_hidden(self):
        """ls сортирует имена, а -a включает скрытые элементы."""
        _, output = self.run_line("ls")
        self.assertEqual(output.splitlines(), [
            "-file", "alpha", "binary", "blank", "docs", "empty", "long"
        ])
        _, output = self.run_line("ls -a")
        self.assertIn(".hidden", output.splitlines())

    def test_ls_long_file_and_empty_directory(self):
        """Длинный вывод показывает тип и размер; пустой каталог допустим."""
        _, output = self.run_line("ls -l alpha")
        self.assertEqual(output, "- 18 alpha\n")
        _, output = self.run_line("ls empty")
        self.assertEqual(output, "")
        _, output = self.run_line("ls -al docs")
        self.assertEqual(output, "d 0 leaf\n")

    def test_ls_multiple_paths_and_partial_error(self):
        """Ошибка одного пути не мешает перечислению остальных."""
        _, output = self.run_line("ls missing docs")
        self.assertIn("docs:\nleaf\n", output)
        self.assertIn("no such file or directory", output)

    def test_cd_absolute_relative_parent_and_previous(self):
        """cd поддерживает абсолютные пути, ., .. и предыдущий каталог."""
        host_cwd = os.getcwd()
        self.run_line("cd /docs/leaf")
        self.assertEqual(self.state.cwd, "/docs/leaf")
        self.run_line("cd ../.")
        self.assertEqual(self.state.cwd, "/docs")
        _, output = self.run_line("cd -")
        self.assertEqual(output, "/docs/leaf\n")
        self.run_line("cd")
        self.assertEqual(self.state.cwd, "/")
        self.assertEqual(os.getcwd(), host_cwd)

    def test_failed_cd_preserves_state(self):
        """Ошибочный переход не изменяет текущий и предыдущий каталоги."""
        self.run_line("cd docs")
        before = self.state.cwd, self.state.previous_cwd
        for line in ("cd /missing", "cd /alpha", "cd docs empty", "cd -z"):
            with self.subTest(line=line):
                self.assertTrue(self.run_line(line)[0])
                self.assertEqual(
                    (self.state.cwd, self.state.previous_cwd), before
                )

    def test_path_components_and_root_boundary(self):
        """Повторные / и .. не позволяют покинуть виртуальный корень."""
        path, node = resolve_path(self.state, "//docs///leaf/../../..")
        self.assertEqual(path, "/")
        self.assertIs(node, self.root)
        self.run_line("cd /docs")
        path, node = resolve_path(self.state, "leaf/./text")
        self.assertEqual(path, "/docs/leaf/text")
        self.assertEqual(node.data, b"last\n")

    def test_traversal_through_file_is_rejected(self):
        """file/.., file/. и завершающий / требуют настоящего каталога."""
        for path in ("alpha/..", "alpha/.", "alpha/", "alpha/child"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(CommandError, "not a directory"):
                    resolve_path(self.state, path)
        with self.assertRaises(CommandError):
            resolve_path(self.state, "")

    def test_cat_preserves_text_and_handles_multiple_files(self):
        """cat сохраняет переносы и не добавляет завершающую новую строку."""
        _, output = self.run_line("cat alpha blank docs/leaf/text")
        self.assertEqual(output, "first\nsecond\nthirdlast\n")
        _, output = self.run_line("cat -- -file")
        self.assertEqual(output, "dash")

    def test_file_errors_do_not_stop_later_operands(self):
        """После ошибки файла обрабатывается следующий файловый операнд."""
        _, output = self.run_line("cat missing docs/leaf/text")
        self.assertIn("last\n", output)
        self.assertIn("no such file or directory", output)
        for path in ("docs", "binary"):
            with self.subTest(path=path):
                with self.assertRaises(CommandError):
                    read_text(self.state, path)

    def test_head_default_custom_zero_and_multiple(self):
        """head поддерживает 10 строк, -n, --lines, ноль и несколько файлов."""
        _, output = self.run_line("head long")
        self.assertEqual(len(output.splitlines()), 10)
        self.assertTrue(output.endswith("line 10\n"))
        _, output = self.run_line("head -n 2 alpha")
        self.assertEqual(output, "first\nsecond\n")
        _, output = self.run_line("head --lines=1 alpha docs/leaf/text")
        self.assertEqual(
            output,
            "==> alpha <==\nfirst\n==> docs/leaf/text <==\nlast\n",
        )
        _, output = self.run_line("head -n 0 alpha")
        self.assertEqual(output, "")

    def test_invalid_arguments_report_errors_and_continue(self):
        """Ошибки опций и операндов сообщаются без завершения сеанса."""
        lines = (
            "ls -z", "cat", "cat -z alpha", "head", "head -n",
            "head -n bad alpha", "head -n -1 alpha", "head -z alpha",
            "uptime x", "exit x",
        )
        for line in lines:
            with self.subTest(line=line):
                result, output = self.run_line(line)
                self.assertTrue(result)
                self.assertTrue(output.startswith(line.split()[0] + ":"))
        self.assertEqual(self.run_line("cat docs/leaf/text")[1], "last\n")

    def test_uptime_is_elapsed_emulated_time(self):
        """uptime использует монотонное время с запуска эмулируемой ОС."""
        self.state.started = 100.0
        with mock.patch("src.commands.time.monotonic", return_value=3761.0):
            _, output = self.run_line("uptime")
        self.assertEqual(output, "up 01:01:01\n")

    def test_prompt_uses_virtual_directory_and_os_identity(self):
        """Приглашение обновляет виртуальный путь после cd."""
        self.run_line("cd docs")
        with mock.patch.object(shell, "get_username", return_value="alice"):
            with mock.patch.object(shell, "get_hostname", return_value="pc"):
                prompt = shell.get_prompt(state=self.state)
        self.assertEqual(prompt, "alice@pc:/docs$ ")
        self.assertEqual(shell.get_prompt("fixed> ", self.state), "fixed> ")


class IntegrationTests(unittest.TestCase):
    """Проверка общего состояния сценария и REPL и сохранности XML."""

    def test_script_state_reaches_repl_and_source_is_unchanged(self):
        """REPL продолжает сценарий в том же каталоге без записи в XML."""
        source = Path(__file__).resolve().parents[1] / "vfs/demo.xml"
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            vfs = folder / "vfs.xml"
            vfs.write_bytes(source.read_bytes())
            script = folder / "startup.txt"
            script.write_text(
                "cd /documents/study/practice\ncat missing\n", encoding="utf-8"
            )
            before = vfs.read_bytes()
            with mock.patch("builtins.input", side_effect=["cat task.txt",
                                                         "exit"]) as reader:
                code, output = call_and_capture(shell.main, [
                    "--vfs-path", str(vfs), "--script", str(script)
                ])
            self.assertEqual(code, 0)
            self.assertIn("Вариант 13\n", output)
            self.assertIn("no such file or directory", output)
            self.assertTrue(
                reader.call_args_list[0].args[0].endswith(
                    ":/documents/study/practice$ "
                )
            )
            self.assertEqual(vfs.read_bytes(), before)
            self.assertEqual(set(folder.iterdir()), {vfs, script})

    def test_head_preserves_non_lf_characters(self):
        """head не считает CR и вертикальную табуляцию отдельными строками."""
        root = Directory("/", {"text": File("text", b"a\rb\vc\nd\n")})
        _, output = call_and_capture(
            shell.execute_line, "head -n 1 text", ShellState(root)
        )
        self.assertEqual(output, "a\rb\vc\n")


if __name__ == "__main__":
    unittest.main()
