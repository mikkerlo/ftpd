#!/usr/bin/env python
from typing import Callable
from typing import List
from dataclasses import dataclass
import os
import socket
import sys

BUFF_SIZE = 4096

ASCII = "ASCII"
BINARY = "Binary"

class ClosedSocketException(Exception):
    pass


class InputSocketConnection(object):
    def __init__(self, socket_data: socket.socket, addr):
        self.buffer = b''
        self.buffer_pos = 0
        self.socket_data = socket_data
        self.addr = addr


    def _get_byte(self):
        if self.buffer_pos >= len(self.buffer):
            self.buffer = self.socket_data.recv(BUFF_SIZE)
            self.buffer_pos = 0
        
        if len(self.buffer) == 0:
            self.say()
            raise ClosedSocketException()

        byte_data = self.buffer[self.buffer_pos]
        self.buffer_pos += 1
        return byte_data


    def _get_command(self) -> bytearray:
        cur_command = bytearray()

        while cur_command[-2:] != b'\r\n':
            cur_command.append(self._get_byte())

        return cur_command


    def say(self, text: str):
        raw_text = text.encode()
        if text[-2:] != b'\r\n':
            raw_text = (text + '\r\n').encode()
        
        self.socket_data.sendall(raw_text)


    def close(self):
        self.socket_data.shutdown(socket.SHUT_RDWR)
        self.socket_data.close()


@dataclass
class FTPContext(object):
    username: str
    is_logged: bool
    cwd: str
    command: str
    args: List[str]
    mode: str
    ip: str
    port: int
    control_connection: InputSocketConnection


def auth(ctx: FTPContext) -> FTPContext:
    return ctx


def check_auth(ctx: FTPContext) -> FTPContext:
    return ctx


def auth_required(f: Callable[[FTPContext], FTPContext]):
    auth_required = os.getenv("HW1_AUTH_DISABLED") or True
    if auth_required:
        def wrapper(ctx: FTPContext) -> FTPContext:
            ctx = check_auth(ctx)
            return f(ctx)
    return f


def args_length(l: int) -> Callable[[FTPContext], FTPContext]:
    def wrapper1(f: Callable[[FTPContext], FTPContext]) -> FTPContext:
        def wrapper2(ctx: FTPContext) -> FTPContext:
            if len(ctx.args) != l:
                ctx.control_connection.say(f"500 Unrecognised {ctx.command} command.")
                ctx.command = None
                ctx.args = []
                return ctx
            return f(ctx)
        return wrapper2
    return wrapper1


@auth_required
def syst_command(ctx: FTPContext) -> FTPContext:
    ctx.control_connection.say("215 UNIX Type: L8")
    return ctx


@auth_required
def noop_command(ctx: FTPContext) -> FTPContext:
    ctx.control_connection.say("200 We have started to count useful tasks in our network course.")
    return ctx


@auth_required
def quit_command(ctx: FTPContext) -> FTPContext:
    ctx.control_connection.say("221 Goodbye.")
    ctx.control_connection.close()
    return ctx


@auth_required
@args_length(1)
def type_command(ctx: FTPContext) -> FTPContext:
    typed = ctx.args[0].upper()
    data = {
        'A': ASCII,
        'I': BINARY,
    }

    if typed in data:
        ctx.mode = data[typed]
        ctx.control_connection.say(f'200 Switching to {ctx.mode} mode.')
    return ctx


@auth_required
@args_length(1)
def stru_command(ctx: FTPContext) -> FTPContext:
    typed = ctx.args[0].upper()
    if typed == "F":
        ctx.control_connection.say("200 Structure set to F.")
    else:
        ctx.control_connection.say("504 1975 have ringed the bell.")
    
    return ctx


@auth_required
@args_length(1)
def port_command(ctx: FTPContext) -> FTPContext:
    raw_ip_info = ctx.args[0].split(',')
    if len(raw_ip_info) != 6:
        ctx.control_connection.say('504 Wrong ip or port format.')
    
    for i in map(int, raw_ip_info):
        if 0 <= i <= 255:
            ctx.control_connection.say('504 Wrong ip or port format.')

    ctx.ip = '.'.join(list(map(int, raw_ip_info))[:4])
    ctx.port = int(raw_ip_info[4]) * 256 + int(raw_ip_info[5])
    
    return ctx


@auth_required
def stor_command(ctx: FTPContext) -> FTPContext:
    if ctx.port is None or ctx.ip is None:
        ctx.control_connection.say('425 Use PORT or PASV first.')
        return ctx

    raw_path = ' '.join(ctx.args)
    abs_path = os.path.abspath(raw_path)
    if not ctx.cwd.startswith(abs_path):
        ctx.control_connection.say('550 Failed to open file.')
        return ctx

    ctx.control_connection.say('150 Here comes the train.')
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_connection:
        data_connection.connect((ctx.ip, ctx.port))
        with open(abs_path, 'wb') as fout:
            data = data_connection.recv(4096)
            while len(data) > 0:
                fout.write(data)
                data = data_connection.recv(4096)

    ctx.control_connection('226 STOR file ok.')
        
    ctx.ip = None
    ctx.port = None
    return ctx


@auth_required
def retr_command(ctx: FTPContext) -> FTPContext:
    if ctx.port is None or ctx.ip is None:
        ctx.control_connection.say('425 Use PORT or PASV first.')
        return ctx

    raw_path = ' '.join(ctx.args)
    abs_path = os.path.abspath(os.path.join(ctx.cwd, raw_path))
    if not ctx.cwd.startswith(abs_path):
        ctx.control_connection.say('550 Failed to open file.')
        return ctx

    ctx.control_connection.say('150 Here comes the file.')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as data_connection:
        data_connection.connect((ctx.ip, ctx.port))
        data = fin.read(4096)
        with open(abs_path, 'rb') as fin:
            data_connection.sendall(data)
            data = fin.read(4096)

    ctx.control_connection('226 RETR file ok.')

    ctx.port = None
    ctx.ip = None
    return ctx


class Connection(object):
    def __init__(self, socket_data: socket.socket, addr):
        self.ctx = FTPContext(
            control_connection = InputSocketConnection(socket_data, addr),
            username = None,
            is_logged = False,
            cwd = os.path.abspath('.'),
            mode = ASCII,
            ip = None,
            port = None,
            command = None,
            args = [],
        )

    # username: str
    # is_logged: bool
    # cwd: str
    # command: str
    # args: List[str]
    # mode: str
    # ip: str
    # port: int
    # control_connection: InputSocketConnection


    def _process_command(self):
        raw_command = self.ctx.control_connection._get_command()
        command = raw_command.decode('ascii').strip()
        command_line = command.split()
        control_command = command_line[0].upper()

        commands = {
            'USER': auth,
            'PASS': auth,
            'SYST': syst_command,
            'NOOP': noop_command,
            'QUIT': quit_command,
            'TYPE': type_command, 
            'PORT': port_command,
            'STOR': stor_command,
            'RETR': retr_command,
        }

        if command in commands:
            self.ctx = commands[command](self.ctx)
        else:
            self.ctx.control_connection.say("502 Not implemented.")
       

    def process(self):
        self.ctx.control_connection.say('''220 (Epic mikkerlo's server)''')
        while True:
            self._process_command()
        self.close()


def check_env():
    return True


def listen():
    if not check_env():
        print("Please check env variables", file=sys.stderr)
        return

    host = os.getenv('HW1_HOST') or '127.0.0.1'
    port = os.getenv('HW1_PORT') or 7777
    addr = (host, port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(5)

        while True:
            c, usr_addr = s.accept()
            conn = Connection(c, usr_addr)
            
            try:
                conn.process()
            except ClosedSocketException:
                conn.close()
                print("Connection closed")


def main():
    listen()


if __name__ == "__main__":
    main()

