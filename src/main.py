"""Эмулятор командной оболочки UNIX-подобной ОС."""

import argparse
import getpass
import os
import socket
import sys

if __package__:
    from .commands import COMMANDS as READ_COMMANDS
    from .mutations import COMMANDS as WRITE_COMMANDS
    from .options import require_no_arguments
    from .session import CommandError, ShellState
    from .vfs import VFSError, count_nodes, load_vfs
else:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.commands import COMMANDS as READ_COMMANDS
    from src.mutations import COMMANDS as WRITE_COMMANDS
    from src.options import require_no_arguments
    from src.session import CommandError, ShellState
    from src.vfs import VFSError, count_nodes, load_vfs

DEFAULT_USER = "user"
HOME_MARK = "~"
PATH_SEPARATOR = "/"
PROMPT_END = "$ "
EXIT_COMMAND = "exit"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
SCRIPT_ENCODING = "utf-8"
COMMANDS = {**READ_COMMANDS, **WRITE_COMMANDS}


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


def get_prompt(custom_prompt=None, state=None):
    """Возвращает пользовательское или стандартное приглашение."""
    if custom_prompt is not None:
        return custom_prompt
    user = get_username()
    host = get_hostname()
    directory = state.cwd if state is not None else get_current_dir()
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


def execute_command(name, args, state):
    """Выполняет команду; ошибки сообщаются, exit завершает сеанс."""
    try:
        if name == EXIT_COMMAND:
            require_no_arguments(args)
            return False
        handler = COMMANDS.get(name)
        if handler is None:
            raise CommandError("command not found")
        handler(state, args)
    except CommandError as error:
        print(f"{name}: {error}")
    return True


def execute_line(line, state):
    """Разбирает и выполняет одну строку команды."""
    name, args = parse_command(line)
    if not name:
        return True
    return execute_command(name, args, state)


def run_startup_script(script_path, state, custom_prompt=None):
    """Выполняет сценарий в общем состоянии оболочки, пропуская ошибки."""
    try:
        with open(script_path, encoding=SCRIPT_ENCODING) as script:
            for raw_line in script:
                line = raw_line.rstrip("\r\n")
                print(f"{get_prompt(custom_prompt, state)}{line}")
                if not execute_line(line, state):
                    return False
    except (OSError, UnicodeError) as error:
        print(f"Startup script error: {error}")
    return True


def run_repl(state, custom_prompt=None):
    """Запускает REPL: Ctrl+D завершает работу, Ctrl+C сбрасывает ввод."""
    while True:
        try:
            line = input(get_prompt(custom_prompt, state))
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        if not execute_line(line, state):
            break


def main(arguments=None):
    """Читает настройки, выполняет скрипт и запускает REPL."""
    config = parse_arguments(arguments)
    print_configuration(config)
    try:
        vfs_root = load_vfs(config.vfs_path)
    except VFSError as error:
        print(f"VFS error: {error}")
        return EXIT_FAILURE
    directories, files = count_nodes(vfs_root)
    print(f"VFS loaded: {directories} directories, {files} files")
    state = ShellState(vfs_root)
    if config.script is not None:
        should_continue = run_startup_script(
            config.script, state, config.prompt
        )
        if not should_continue:
            return EXIT_SUCCESS
    run_repl(state, config.prompt)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
