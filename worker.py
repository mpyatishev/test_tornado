# -*- coding: utf-8 -*-

import json
import logging
import os
import queue
import socket
import threading
import time

from concurrent.futures import ThreadPoolExecutor

import tornado
from tornado import (
    gen,
    ioloop,
    tcpserver,
)
from tornado.concurrent import Future

from utils import send_msg, recv_msg


tornado.log.enable_pretty_logging()
logger = logging.getLogger(__name__)

q = queue.Queue()

executor = ThreadPoolExecutor(5)


class Game():
    count = 0

    def __init__(self, worker, sock):
        self.worker = worker
        self.loop = worker.loop
        self.sock = sock
        self.__class__.count += 1
        self.count = self.__class__.count
        logger.info('gameprotocol%s created' % self.count)

        self._init()

    def _init(self):
        self.loop.add_handler(self.sock, self.data_received,
                              ioloop.IOLoop.ERROR | ioloop.IOLoop.READ)
        send_msg(self.sock, 'ok')

    def connection_made(self, transport):
        self.transport = transport
        logger.info('gameprotocol%s: connection made' % self.count)
        # logger.info(self.transport)

    def connection_lost(self, exc):
        client = self.transport.get_extra_info('peername')
        # logger.info(self.transport)
        logger.info('gameprotocol%s: connection to %s closed' % (self.count, client))
        if exc:
            logger.info(exc)

        if self._connection_lost_callback:
            self._connection_lost_callback(client)

    def data_received(self, sock, events):
        if events & ioloop.IOLoop.ERROR:
            logger.info('error')
            self.disconnect(sock)
            return

        data = sock.recv(4096)
        if not data:
            self.disconnect(sock)
            return

        logger.info('gameprotocol%s: %s' % (self.count, data.decode()))
        if 'help!' in data.decode():
            self.loop.add_callback(self.work, sock)

    def disconnect(self, sock):
        self.loop.remove_handler(sock)
        logger.info('client disconnected')
        self.worker.client_disconnected(self.sock)

    @gen.coroutine
    def work(self, sock):
        yield gen.sleep(1)
        logger.info('gameprotocol%s: sending "ok"' % (self.count,))
        sock(json.dumps('ok').encode())

    def eof_received(self):
        # logger.info(self.transport)
        logger.info('gameprotocol%s: eof' % self.count)
        self.transport.close()
        # logger.info('gameprotocol%s: %s' % (self.count, self.transport))

    def set_connection_lost_callback(self, callback):
        self._connection_lost_callback = callback


class Worker:
    def __init__(self, worker, server_sock):
        self.worker = worker
        self.server_sock = server_sock
        self.socks = []
        self.clients = []
        self.tasks = []

        self._init()

        logger.info('worker %s created' % self.worker)

        self.start()

    def _init(self):
        self.loop = ioloop.IOLoop()
        self.loop.add_handler(self.server_sock, self.reader, ioloop.IOLoop.READ)
        self.loop.add_callback(self._main)

    @gen.coroutine
    def _main(self):
        while True:
            yield gen.sleep(1)
            if not self.clients:
                logger.info('shutting down')
                break
        self.loop.stop()

    def start(self):
        self.loop.start()
        send_msg(self.server_sock, {'done': os.getpid()})
        self.server_sock.close()

    def reader(self, server_sock, events):
        data, fds = recv_msg(server_sock)
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
                    sock.setblocking(False)
                    self.socks.append(sock)
                    self.clients.append(sock.getpeername())
                    game = Game(self, sock)
            else:
                logger.info('worker %s received: %s' % (self.worker, msg))

    def client_connected(self, client, future):
        transport, protocol = future.result()
        logger.info('%s %s' % (transport, protocol))
        protocol.set_connection_lost_callback(self.client_disconnected)
        self.clients.append(client)

    def client_disconnected(self, sock):
        client = sock.getpeername()
        data = {'client': client}
        send_msg(self.server_sock, data)
        self.clients.remove(client)


if __name__ == '__main__':
    w = Worker('game-worker0')
    w.run()
