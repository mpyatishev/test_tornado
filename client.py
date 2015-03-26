#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging

import tornado
from tornado import ioloop
from tornado import gen
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.websocket import websocket_connect

logger = logging.getLogger(__name__)


@gen.coroutine
def handle_response(response):
    if response.error:
        logger.info(response.error)
    else:
        request = HTTPRequest('ws://127.0.0.1:8889/battle')
        ws = yield websocket_connect(request)
        body = json.dumps({'token': '1231234'})
        ws.write_message(body)
        while True:
            message = yield ws.read_message()
            logger.info(message)
            if message is None or True:
                break
        ws.close()


if __name__ == '__main__':
    tornado.log.enable_pretty_logging()

    client = AsyncHTTPClient(defaults=dict(
        headers={'Set-Cookie': 'sid=1231234'}
    ))
    client.fetch('http://127.0.0.1:8889', handle_response)

    loop = ioloop.IOLoop.instance()
    try:
        loop.start()
    except KeyboardInterrupt:
        loop.stop()

    client.close()
