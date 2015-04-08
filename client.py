#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import time

import tornado
from tornado import ioloop
from tornado import gen
from tornado.httpclient import HTTPRequest
from tornado.websocket import websocket_connect

logger = logging.getLogger(__name__)
loop = ioloop.IOLoop.instance()
max_clients = 1000


@gen.coroutine
def make_response():
    request = HTTPRequest('ws://127.0.0.1:8889/', headers={
        'Sec-WebSocket-Protocol': 'binary'
    })
    ws = yield websocket_connect(request)
    body = json.dumps({'token': '1231234'}) + '\r\n'
    ws.write_message(body)
    message = yield ws.read_message()
    logger.info(message)
    body = json.dumps('client') + '\r\n'
    ws.write_message(body)
    yield gen.sleep(3)
    body = json.dumps('exit') + '\r\n'
    ws.write_message(body)
    ws.close()


@gen.coroutine
def run():
    futures = []
    for client in range(max_clients):
        futures.append(make_response())

    yield futures
    loop.stop()


if __name__ == '__main__':
    tornado.log.enable_pretty_logging()

    loop.add_callback(run)
    try:
        loop.start()
    except KeyboardInterrupt:
        loop.stop()
