#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import array
import copy
import functools
import hashlib
import json
import logging
import time
import os
import socket
import sys

import tornado
from tornado import (
    gen,
    ioloop,
    tcpserver,
)

from utils import send_msg, recv_msg

logger = logging.getLogger(__name__)
DIR_PREFIX = os.path.dirname(os.path.dirname(__file__))


class Server(tcpserver.TCPServer):
    _pids = {}

    def handle_stream(self, stream, address):
        socks = socket.socketpair()
        pid = os.fork()
        if pid:
            stream.close()
            socks[1].close()
            self._pids[socks[0]] = pid
            self.io_loop.add_handler(socks[0], functools.partial(self.waitpid, pid),
                                     ioloop.IOLoop.READ)
        else:
            socks[0].close()
            self.server_sock = socks[1]
            self.io_loop.add_callback(functools.partial(self.work, stream))

    @gen.coroutine
    def socket_handler(self):
        logger.info(self.socket_handler)

    @gen.coroutine
    def waitpid(self, pid, fd, events):
        self.io_loop.remove_handler(fd)
        logger.info('waiting %s' % pid)
        res = os.waitpid(pid, 0)
        logger.info('%s died' % pid)
        return res

    def send_stream(self):
        sock, pid = self._pids.popitem()

        self.send_sock(sock)
        tmp_stream = copy.deepcopy(self.stream)

        self._pids[sock] = pid

    def send_sock(self, worker_sock):
        sock = self.stream.fileno()
        msg = {
            'sock': True,
            'family': sock.family,
            'type': sock.type,
            'proto': sock.proto,
        }
        fds = [sock.fileno()]
        send_msg(worker_sock, msg, [(socket.SOL_SOCKET,
                                     socket.SCM_RIGHTS, array.array("i", fds))])

    def reader(self):
        data, fds = recv_msg(self.server_sock)
        for msg in data.decode().split("\r\n"):
            if not msg:
                continue
            try:
                msg = json.loads(msg)
            except ValueError as e:
                logger.info(e)
                continue
            if 'sock' in msg:
                family = msg['family']
                type = msg['type']
                proto = msg['proto']
                for fd in fds:
                    sock = socket.fromfd(fd, family, type, proto)
            else:
                logger.info('worker %s received: %s' % (self.worker, msg))

    def on_message(self, message):
        # logger.info(self.on_message)
        # logger.info(self.stream)
        self.write_message('your message: ' + message)

        try:
            message = json.loads(message)
        except Exception as e:
            logger.info(e)

        if message and 'token' in message:
            logger.info(message['token'])
            if not self._pids:
                self.fork()
            else:
                self.send_stream()
        elif message:
            logger.info('child %s: %s' % (os.getpid(), message))
            if message == 'exit':
                self.stream.io_loop.call_later(1, functools.partial(os._exit, os.EX_OK))
                self.serv_sock.sendmsg(['done'.encode()])

    @gen.coroutine
    def work(self, stream):
        while True:
            message = yield stream.read_until(delimiter='\r\n\r\n'.encode())
            message = message.decode()

            try:
                message = json.loads(message)
            except Exception as e:
                logger.info(e)

            if message and 'token' in message:
                logger.info(message['token'])
                yield stream.write(json.dumps('ok').encode())
            elif message:
                logger.info('child %s: %s' % (os.getpid(), message))
                if message == 'exit':
                    stream.close()
                    self.server_sock.sendmsg(['done'.encode()])
                    self.server_sock.close()
                    self.io_loop.call_later(1, functools.partial(os._exit, os.EX_OK))
                    logger.info('exiting...')
                    break


def main():
    tornado.log.enable_pretty_logging()
    server = Server()
    server.bind(8890)
    server.start(1)
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        ioloop.IOLoop.instance().stop()


if __name__ == '__main__':
    main()
