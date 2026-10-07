"""Тесты эмулятора командной оболочки."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

from src import main as shell
from pathlib import Path

VFS_PATH = str(Path(__file__).resolve().parents[1] / "vfs" / "minimal.xml")


def call_and_capture(func, *args):
    """Вызывает func и возвращает пару (результат, вывод в stdout)."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        result = func(*args)
    return result, buffer.getvalue()


class ParseCommandTests(unittest.TestCase):
    """Проверка разбора строки на команду и аргументы."""

    def test_command_without_arguments(self):
        """Команда без аргументов."""
        self.assertEqual(shell.parse_command("ls"), ("ls", []))

    def test_command_with_arguments(self):
        """Команда с несколькими аргументами."""
        self.assertEqual(
            shell.parse_command("ls -l /tmp"), ("ls", ["-l", "/tmp"])
        )

    def test_extra_whitespace(self):
        """Лишние пробелы и табуляция не влияют на результат."""
        self.assertEqual(
            shell.parse_command("  cd \t  docs  "), ("cd", ["docs"])
        )

    def test_empty_line(self):
        """Пустая строка и строка из пробелов дают пустую команду."""
        self.assertEqual(shell.parse_command(""), ("", []))
        self.assertEqual(shell.parse_command("   "), ("", []))


class PromptTests(unittest.TestCase):
    """Проверка формирования приглашения к вводу."""

    def test_prompt_format(self):
        """Приглашение имеет вид user@host:dir$ ."""
        with mock.patch.object(shell, "get_username", return_value="alice"):
            with mock.patch.object(shell, "get_hostname", return_value="pc"):
                with mock.patch.object(
                    shell, "get_current_dir", return_value="~/work"
                ):
                    self.assertEqual(shell.get_prompt(), "alice@pc:~/work$ ")

    def test_custom_prompt(self):
        """Пользовательское приглашение заменяет стандартное."""
        self.assertEqual(shell.get_prompt("vfs> "), "vfs> ")

    def test_username_fallback(self):
        """Если имя пользователя не определить, берётся запасное значение."""
        with mock.patch("getpass.getuser", side_effect=OSError):
            self.assertEqual(shell.get_username(), shell.DEFAULT_USER)

    def test_hostname_from_os(self):
        """Имя компьютера берётся из реальной ОС."""
        with mock.patch("socket.gethostname", return_value="my-host"):
            self.assertEqual(shell.get_hostname(), "my-host")


class CurrentDirTests(unittest.TestCase):
    """Проверка отображения текущего каталога в приглашении."""

    def setUp(self):
        """Задаёт условный домашний каталог."""
        self.home = os.path.join(os.sep, "home", "alice")

    def check_dir(self, cwd, expected):
        """Проверяет результат get_current_dir для заданного cwd."""
        with mock.patch("os.getcwd", return_value=cwd):
            with mock.patch("os.path.expanduser", return_value=self.home):
                self.assertEqual(shell.get_current_dir(), expected)

    def test_home_directory(self):
        """Домашний каталог отображается как ~."""
        self.check_dir(self.home, "~")

    def test_inside_home(self):
        """Вложенный каталог отображается относительно ~."""
        self.check_dir(os.path.join(self.home, "work"), "~/work")

    def test_outside_home(self):
        """Каталог вне домашнего отображается полным путём."""
        self.check_dir(os.path.join(os.sep, "tmp"), "/tmp")


class ExecuteCommandTests(unittest.TestCase):
    """Проверка выполнения команд."""

    def test_exit_stops_shell(self):
        """Команда exit сообщает о необходимости завершения."""
        result, output = call_and_capture(shell.execute_command, "exit", [])
        self.assertFalse(result)
        self.assertEqual(output, "")

    def test_ls_stub(self):
        """Заглушка ls выводит своё имя и аргументы."""
        result, output = call_and_capture(
            shell.execute_command, "ls", ["a.txt", "b.txt"]
        )
        self.assertTrue(result)
        self.assertEqual(
            output, "Command: ls\nArguments: ['a.txt', 'b.txt']\n"
        )

    def test_cd_stub(self):
        """Заглушка cd выводит своё имя и аргументы."""
        result, output = call_and_capture(
            shell.execute_command, "cd", ["docs"]
        )
        self.assertTrue(result)
        self.assertEqual(output, "Command: cd\nArguments: ['docs']\n")

    def test_stub_without_arguments(self):
        """Заглушка без аргументов выводит пустой список."""
        _, output = call_and_capture(shell.execute_command, "ls", [])
        self.assertEqual(output, "Command: ls\nArguments: []\n")

    def test_unknown_command(self):
        """Неизвестная команда даёт сообщение об ошибке, работа продолжается."""
        result, output = call_and_capture(
            shell.execute_command, "foo", ["bar"]
        )
        self.assertTrue(result)
        self.assertEqual(output, "foo: command not found\n")


class ConfigurationTests(unittest.TestCase):
    """Проверка параметров командной строки и их вывода."""

    def test_default_arguments(self):
        """Остальные параметры необязательны."""
        config = shell.parse_arguments(["--vfs-path", VFS_PATH])
        self.assertEqual(config.vfs_path, VFS_PATH)
        self.assertIsNone(config.prompt)
        self.assertIsNone(config.script)

    def test_all_arguments(self):
        """Все поддерживаемые флаги сохраняют переданные значения."""
        config = shell.parse_arguments(
            [
                "--vfs-path",
                "vfs.xml",
                "--prompt",
                "demo> ",
                "--script",
                "startup.txt",
            ]
        )
        self.assertEqual(config.vfs_path, "vfs.xml")
        self.assertEqual(config.prompt, "demo> ")
        self.assertEqual(config.script, "startup.txt")

    def test_configuration_output(self):
        """При запуске выводятся все три параметра."""
        config = shell.parse_arguments(
            ["--vfs-path", "vfs.xml", "--prompt", "demo> "]
        )
        _, output = call_and_capture(shell.print_configuration, config)
        self.assertEqual(
            output,
            "Configuration:\n"
            "  VFS path: vfs.xml\n"
            "  Prompt: demo> \n"
            "  Startup script: None\n",
        )


class StartupScriptTests(unittest.TestCase):
    """Проверка последовательного выполнения стартового скрипта."""

    def setUp(self):
        """Создаёт временный каталог для файлов сценариев."""
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        """Удаляет временные файлы сценариев."""
        self.temp_dir.cleanup()

    def create_script(self, contents):
        """Создаёт стартовый скрипт с заданным содержимым."""
        path = os.path.join(self.temp_dir.name, "startup.txt")
        with open(path, "w", encoding=shell.SCRIPT_ENCODING) as script:
            script.write(contents)
        return path

    def test_commands_and_errors_are_shown(self):
        """После ошибочной команды выполняются следующие строки."""
        path = self.create_script("ls one\nunknown\ncd docs\n")
        result, output = call_and_capture(
            shell.run_startup_script, path, "demo> "
        )
        self.assertTrue(result)
        self.assertEqual(
            output,
            "demo> ls one\n"
            "Command: ls\n"
            "Arguments: ['one']\n"
            "demo> unknown\n"
            "unknown: command not found\n"
            "demo> cd docs\n"
            "Command: cd\n"
            "Arguments: ['docs']\n",
        )

    def test_exit_stops_script(self):
        """Команда exit не позволяет выполнить оставшиеся строки."""
        path = self.create_script("exit\nls ignored\n")
        result, output = call_and_capture(
            shell.run_startup_script, path, "demo> "
        )
        self.assertFalse(result)
        self.assertEqual(output, "demo> exit\n")

    def test_missing_script_reports_error(self):
        """Ошибка открытия сценария выводится, работа может продолжиться."""
        path = os.path.join(self.temp_dir.name, "missing.txt")
        result, output = call_and_capture(
            shell.run_startup_script, path, "demo> "
        )
        self.assertTrue(result)
        self.assertIn("Startup script error:", output)
        self.assertIn("missing.txt", output)


class ReplTests(unittest.TestCase):
    """Проверка цикла чтения и выполнения команд."""

    def run_with_input(self, inputs):
        """Запускает REPL с заданными вводами и возвращает вывод."""
        with mock.patch("builtins.input", side_effect=inputs) as fake_input:
            _, output = call_and_capture(shell.run_repl)
        self.fake_input = fake_input
        return output

    def test_commands_then_exit(self):
        """Команды выполняются по очереди, пустые строки пропускаются."""
        output = self.run_with_input(["ls x", "", "foo", "exit"])
        self.assertEqual(
            output,
            "Command: ls\nArguments: ['x']\nfoo: command not found\n",
        )

    def test_exit_stops_reading(self):
        """После exit ввод больше не читается."""
        self.run_with_input(["exit", "ls"])
        self.assertEqual(self.fake_input.call_count, 1)

    def test_eof_stops_shell(self):
        """Конец ввода (Ctrl+D) завершает работу."""
        output = self.run_with_input(EOFError)
        self.assertEqual(output, "\n")

    def test_keyboard_interrupt_continues(self):
        """Ctrl+C сбрасывает строку, но не завершает работу."""
        output = self.run_with_input([KeyboardInterrupt, "exit"])
        self.assertEqual(output, "\n")
        self.assertEqual(self.fake_input.call_count, 2)

    def test_custom_prompt_is_used(self):
        """REPL передаёт input пользовательское приглашение."""
        with mock.patch(
            "builtins.input", side_effect=["exit"]
        ) as fake_input:
            call_and_capture(shell.run_repl, "demo> ")
        fake_input.assert_called_once_with("demo> ")


class MainTests(unittest.TestCase):
    """Проверка точки входа."""

    def test_missing_vfs_parameter(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                shell.main([])
        self.assertEqual(error.exception.code, 2)

    def test_vfs_error_stops_before_script_and_repl(self):
        with mock.patch.object(shell, "run_startup_script") as script:
            with mock.patch.object(shell, "run_repl") as repl:
                result, output = call_and_capture(shell.main, [
                    "--vfs-path", VFS_PATH + ".missing", "--script", "startup.txt"
                ])
        self.assertEqual(result, 1)
        self.assertIn("VFS error:", output)
        script.assert_not_called()
        repl.assert_not_called()

    def test_invalid_vfs_stops_before_repl(self):
        path = str(Path(VFS_PATH).with_name("invalid.xml"))
        with mock.patch.object(shell, "run_repl") as repl:
            result, output = call_and_capture(shell.main, ["--vfs-path", path])
        self.assertEqual(result, 1)
        self.assertIn("VFS error:", output)
        repl.assert_not_called()

    def test_vfs_is_loaded_before_startup_script(self):
        with mock.patch.object(shell, "load_vfs", wraps=shell.load_vfs) as loader:
            def run_script(*args):
                loader.assert_called_once_with(VFS_PATH)
                return False
            with mock.patch.object(shell, "run_startup_script", side_effect=run_script):
                result, _ = call_and_capture(shell.main, [
                    "--vfs-path", VFS_PATH, "--script", "startup.txt"
                ])
        self.assertEqual(result, 0)

    def test_main_returns_success(self):
        """main возвращает код успешного завершения."""
        with mock.patch("builtins.input", side_effect=["exit"]):
            result, _ = call_and_capture(shell.main, ["--vfs-path", VFS_PATH])
        self.assertEqual(result, shell.EXIT_SUCCESS)

    def test_main_runs_script_before_repl(self):
        """exit в стартовом сценарии завершает эмулятор до REPL."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "startup.txt")
            with open(
                path, "w", encoding=shell.SCRIPT_ENCODING
            ) as script:
                script.write("exit\n")
            arguments = [
                "--vfs-path",
                VFS_PATH,
                "--prompt",
                "demo> ",
                "--script",
                path,
            ]
            result, output = call_and_capture(shell.main, arguments)
        self.assertEqual(result, shell.EXIT_SUCCESS)
        self.assertIn(f"VFS path: {VFS_PATH}", output)
        self.assertIn("Prompt: demo> ", output)
        self.assertIn(f"Startup script: {path}", output)
        self.assertTrue(output.endswith("demo> exit\n"))


if __name__ == "__main__":
    unittest.main()

