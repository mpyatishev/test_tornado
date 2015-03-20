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
        logger.info('herer')
        time.sleep(5)
        self.render('index.html')


class Application(web.Application):
    def __init__(self):
        handlers = [
            (r'/', BattleHandler),
        ]
        conf = dict(
            template_path=TEMPLATE_PATH,
            static_path=STATIC_PATH,
            autoescape=True,
            debug=True,
        )

        web.Application.__init__(self, handlers, **conf)


class HTTPServer(httpserver.HTTPServer):
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
            super().handle_stream(stream, address)
            socks[1].sendmsg('done'.encode())
            logger.info('child died')
            os._exit(os.EX_OK)

    @gen.coroutine
    def waitpid(self, pid, fd, events):
        logger.info(pid)
        logger.info(self._pids[fd])
        self.io_loop.remove_handler(fd)
        return os.waitpid(pid, 0)


def main():
    tornado.log.enable_pretty_logging()
    application = Application()
    http_server = HTTPServer(application)
    http_server.bind(8889)
    http_server.start(1)
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
