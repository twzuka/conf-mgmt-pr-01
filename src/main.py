"""Эмулятор командной оболочки UNIX-подобной ОС (этап 1: REPL)."""

import getpass
import os
import socket
import sys

DEFAULT_USER = "user"
HOME_MARK = "~"
PATH_SEPARATOR = "/"
PROMPT_END = "$ "
EXIT_COMMAND = "exit"
EXIT_SUCCESS = 0


def get_username():
    """Возвращает имя текущего пользователя реальной ОС.

    Если определить имя не удалось, возвращает DEFAULT_USER.
    """
    try:
        return getpass.getuser()
    except (KeyError, OSError, ImportError):
        return DEFAULT_USER


def get_hostname():
    """Возвращает имя компьютера, на котором запущен эмулятор."""
    return socket.gethostname()


def get_current_dir():
    """Возвращает текущий каталог для приглашения.

    Домашний каталог заменяется на «~», разделители пути приводятся
    к виду UNIX («/»).
    """
    cwd = os.getcwd()
    home = os.path.expanduser(HOME_MARK)
    if cwd == home:
        return HOME_MARK
    if cwd.startswith(home + os.sep):
        cwd = HOME_MARK + cwd[len(home):]
    return cwd.replace(os.sep, PATH_SEPARATOR)


def get_prompt():
    """Формирует приглашение к вводу вида «username@hostname:~$ »."""
    user = get_username()
    host = get_hostname()
    directory = get_current_dir()
    return f"{user}@{host}:{directory}{PROMPT_END}"


def parse_command(line):
    """Разделяет введённую строку на команду и список аргументов.

    Разделителем служат пробельные символы. Для пустой строки
    возвращает пустое имя команды и пустой список аргументов.
    """
    parts = line.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def print_stub(name, args):
    """Выводит имя команды-заглушки и переданные ей аргументы."""
    print(f"Command: {name}")
    print(f"Arguments: {args}")


def command_ls(args):
    """Заглушка команды ls."""
    print_stub("ls", args)


def command_cd(args):
    """Заглушка команды cd."""
    print_stub("cd", args)


COMMANDS = {
    "ls": command_ls,
    "cd": command_cd,
}


def execute_command(name, args):
    """Выполняет команду.

    Возвращает False, если эмулятор нужно завершить (команда exit),
    иначе True. Для неизвестной команды выводит сообщение об ошибке.
    """
    if name == EXIT_COMMAND:
        return False
    handler = COMMANDS.get(name)
    if handler is None:
        print(f"{name}: command not found")
    else:
        handler(args)
    return True


def run_repl():
    """Запускает цикл «чтение — выполнение — вывод».

    Ctrl+D завершает работу, Ctrl+C сбрасывает текущую строку ввода.
    """
    while True:
        try:
            line = input(get_prompt())
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        name, args = parse_command(line)
        if name and not execute_command(name, args):
            break


def main():
    """Точка входа: запускает REPL и возвращает код завершения."""
    run_repl()
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
