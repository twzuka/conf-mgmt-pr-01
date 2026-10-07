"""Эмулятор командной оболочки UNIX-подобной ОС."""

import argparse
import getpass
import os
import socket
import sys

if __package__:
    from .vfs import VFSError, count_nodes, load_vfs
else:
    from vfs import VFSError, count_nodes, load_vfs

DEFAULT_USER = "user"
HOME_MARK = "~"
PATH_SEPARATOR = "/"
PROMPT_END = "$ "
EXIT_COMMAND = "exit"
EXIT_SUCCESS = 0
SCRIPT_ENCODING = "utf-8"


def create_argument_parser():
    """Создаёт парсер параметров командной строки."""
    parser = argparse.ArgumentParser(
        description="UNIX-like shell emulator"
    )
    parser.add_argument(
        "--vfs-path",
        required=True,
        help="path to the physical VFS location",
    )
    parser.add_argument(
        "--prompt",
        help="custom input prompt",
    )
    parser.add_argument(
        "--script",
        help="path to the startup script",
    )
    return parser


def parse_arguments(arguments=None):
    """Разбирает параметры командной строки."""
    return create_argument_parser().parse_args(arguments)


def print_configuration(config):
    """Выводит заданные параметры для отладки."""
    print("Configuration:")
    print(f"  VFS path: {config.vfs_path}")
    print(f"  Prompt: {config.prompt}")
    print(f"  Startup script: {config.script}")


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


def get_prompt(custom_prompt=None):
    """Возвращает пользовательское или стандартное приглашение."""
    if custom_prompt is not None:
        return custom_prompt
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


def execute_line(line):
    """Разбирает и выполняет одну строку команды."""
    name, args = parse_command(line)
    if not name:
        return True
    return execute_command(name, args)


def run_startup_script(script_path, custom_prompt=None):
    """Выполняет команды стартового скрипта по порядку."""
    try:
        with open(script_path, encoding=SCRIPT_ENCODING) as script:
            for raw_line in script:
                line = raw_line.rstrip("\r\n")
                print(f"{get_prompt(custom_prompt)}{line}")
                if not execute_line(line):
                    return False
    except (OSError, UnicodeError) as error:
        print(f"Startup script error: {error}")
    return True


def run_repl(custom_prompt=None):
    """Запускает цикл «чтение — выполнение — вывод».

    Ctrl+D завершает работу, Ctrl+C сбрасывает текущую строку ввода.
    """
    while True:
        try:
            line = input(get_prompt(custom_prompt))
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        if not execute_line(line):
            break


def main(arguments=None):
    """Читает настройки, выполняет скрипт и запускает REPL."""
    config = parse_arguments(arguments)
    print_configuration(config)
    try:
        vfs_root = load_vfs(config.vfs_path)
    except VFSError as error:
        print(f"VFS error: {error}")
        return 1
    directories, files = count_nodes(vfs_root)
    print(f"VFS loaded: {directories} directories, {files} files")
    # vfs_root остаётся в памяти до завершения main.
    if config.script is not None:
        should_continue = run_startup_script(
            config.script, config.prompt
        )
        if not should_continue:
            return EXIT_SUCCESS
    run_repl(config.prompt)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())

