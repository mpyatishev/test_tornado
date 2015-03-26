#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    httpserver,
    web,
    websocket,
)

logger = logging.getLogger(__name__)
DIR_PREFIX = os.path.dirname(os.path.dirname(__file__))
TEMPLATE_PATH = os.path.join(DIR_PREFIX, "templates")
STATIC_PATH = os.path.join(DIR_PREFIX, "static")


class BattleHandler(web.RequestHandler):
    @web.asynchronous
    @gen.coroutine
    def get(self):
        self.xsrf_token
        logger.info('entered %s' % self)
        time.sleep(5)
        self.render('index.html')
        logger.info('exiting %s' % self)


class WebSocketHandler(websocket.WebSocketHandler):
    def open(self):
        logger.info('Websocket opened')
        logger.info(self.request.connection)
        logger.info(self.stream)

    def on_message(self, message):
        logger.info(self.on_message)
        logger.info(self.stream)
        self.write_message('your message: ' + message)

        try:
            message = json.loads(message)
        except Exception as e:
            logger.info(e)

        if message and 'token' in message:
            logger.info(message['token'])

    def on_close(self):
        logger.info('Websocket closed')


class Application(web.Application):
    def __init__(self):
        handlers = [
            (r'/', BattleHandler),
            (r'/battle', WebSocketHandler),
        ]
        conf = dict(
            template_path=TEMPLATE_PATH,
            static_path=STATIC_PATH,
            autoescape=True,
            debug=True,
            autoreload=False,
        )

        web.Application.__init__(self, handlers, **conf)

    def start_request(self, server_conn, request_conn):
        logger.info(server_conn)
        logger.info(request_conn)
        return super().start_request(server_conn, request_conn)


class HTTPServer(httpserver.HTTPServer):
    _pids = {}

    def _handle_connection(self, connection, address):
        logger.info('%s %s' % (connection, address))
        return super()._handle_connection(connection, address)

    def handle_stream(self, stream, address):
        logger.info(stream)
        return super().handle_stream(stream, address)

    def __handle_stream(self, stream, address):
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
            super().handle_stream(stream, address)
            socks[1].sendmsg(['done'.encode()])
            logger.info('child died')
            os._exit(os.EX_OK)

    @gen.coroutine
    def waitpid(self, pid, fd, events):
        logger.info(pid)
        self.io_loop.remove_handler(fd)
        return os.waitpid(pid, 0)


def main():
    tornado.log.enable_pretty_logging()
    application = Application()
    http_server = HTTPServer(application)
    http_server.bind(8889)
    http_server.start(1)
    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        ioloop.IOLoop.instance().stop()


if __name__ == '__main__':
    main()
