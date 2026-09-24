"""Тесты эмулятора командной оболочки (этап 1)."""

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from src import main as shell


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


class MainTests(unittest.TestCase):
    """Проверка точки входа."""

    def test_main_returns_success(self):
        """main возвращает код успешного завершения."""
        with mock.patch("builtins.input", side_effect=["exit"]):
            result, _ = call_and_capture(shell.main)
        self.assertEqual(result, shell.EXIT_SUCCESS)


if __name__ == "__main__":
    unittest.main()
