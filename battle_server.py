#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import array
import copy
import functools
import hashlib
import heapq
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

from worker import Worker
from utils import send_msg, recv_msg

logger = logging.getLogger(__name__)


class Server(tcpserver.TCPServer):
    max_clients = 10
    workers = []
    clients_to_workers = {}
    socks_to_workers = {}
    pids_to_workers = {}

    def handle_stream(self, stream, address):
        self.stream = stream
        self.io_loop.add_handler(stream.socket, self.data_received,
                                 ioloop.IOLoop.READ | ioloop.IOLoop.ERROR)

    @gen.coroutine
    def data_received(self, socket, events):
        self.io_loop.remove_handler(socket)

        if events & ioloop.IOLoop.ERROR:
            logger.info('server: client disconnected')
        else:
            try:
                message, fds = recv_msg(socket)
            except OSError:
                pass
                # logger.info(socket)
            else:
                try:
                    message = json.loads(message.decode())
                except Exception as e:
                    logger.info(e)

                if message and 'token' in message:
                    logger.info(message['token'])
                    worker = self.get_worker()
                    command = {'queue': message['token']}
                    self.send_msg(worker, command)
                    self.send_sock(worker)
                    client = socket.getpeername()
                    self.clients_to_workers[client] = worker
                else:
                    logger.info(message)

        self.stream.close()
        socket.close()

    def get_worker(self):
        try:
            clients, worker = heapq.heappop(self.workers)
        except IndexError:
            clients = None

        if clients is None or clients >= self.max_clients:
            if clients is not None:
                heapq.heappush(self.workers, (clients, worker))
            clients = 0
            worker = self.create_worker()
            self.run_worker(worker)

        heapq.heappush(self.workers, (clients + 1, worker))

        return worker

    def create_worker(self):
        return 'game-worker%s' % len(self.workers)

    def run_worker(self, worker):
        socks = socket.socketpair()
        self.socks_to_workers[worker] = socks[0]
        pid = os.fork()
        if pid:
            self.pids_to_workers[worker] = pid
            socks[1].close()
            self.io_loop.add_handler(socks[0], self.reader, ioloop.IOLoop.READ)
        else:
            socks[0].close()
            self.io_loop.stop()
            # self.io_loop.close()
            Worker(worker, socks[1])
            os._exit(os.EX_OK)

    def send_msg(self, worker, msg, *args):
        worker_sock = self.socks_to_workers[worker]
        send_msg(worker_sock, msg)

    def send_sock(self, worker):
        sock = self.stream.socket
        # logger.info(sock)
        msg = {
            'sock': True,
            'family': sock.family,
            'type': sock.type,
            'proto': sock.proto,
        }
        fds = [sock.fileno()]
        worker_sock = self.socks_to_workers[worker]
        send_msg(worker_sock, msg, [(socket.SOL_SOCKET,
                                     socket.SCM_RIGHTS, array.array("i", fds))])

    def reader(self, sock, events):
        msg, fds = recv_msg(sock)
        # logger.info('dispatcher: %s' % msg.decode())
        for data in msg.decode().split('\r\n'):
            if not data:
                continue
            data = json.loads(data)
            if 'client' in data:
                self.client_disconnected(data['client'])
            elif 'done' in data:
                pid = data['done']
                worker = self.get_worker_by_pid(pid)
                self.worker_done(worker)

    def client_disconnected(self, client):
        if not isinstance(client, tuple):
            client = tuple(client)

        worker = self.clients_to_workers.pop(client, None)
        if worker is not None:
            for (clients, w) in self.workers:
                if w == worker:
                    self.workers.remove((clients, w))
                    clients -= 1
                    heapq.heappush(self.workers, (clients, w))
                    break

    def get_worker_by_pid(self, pid):
        for (worker, wpid) in self.pids_to_workers.items():
            if wpid == pid:
                return worker

    def worker_done(self, worker):
        os.waitpid(self.pids_to_workers[worker], 0)
        logger.info('%s done' % worker)
        self.io_loop.remove_handler(self.socks_to_workers[worker])
        self.socks_to_workers[worker].close()
        del self.socks_to_workers[worker]
        for (clients, w) in self.workers:
            if w == worker:
                self.workers.remove((clients, w))
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
