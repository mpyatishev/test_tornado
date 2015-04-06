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


@gen.coroutine
def handle_response(response=None):
    if response and response.error:
        logger.info(response.error)
    else:
        request = HTTPRequest('ws://127.0.0.1:8889/', headers={
            'Sec-WebSocket-Protocol': 'binary'
        })
        ws = yield websocket_connect(request)
        body = json.dumps({'token': '1231234'}) + '\r\n\r\n'
        ws.write_message(body)
        while True:
            message = yield ws.read_message()
            logger.info(message)
            time.sleep(1)
            body = json.dumps('client') + '\r\n\r\n'
            ws.write_message(body)
            time.sleep(1)
            body = json.dumps('exit') + '\r\n\r\n'
            ws.write_message(body)
            if message is None or True:
                break
        yield gen.sleep(1)
        ws.close()

    loop.stop()


if __name__ == '__main__':
    tornado.log.enable_pretty_logging()

    loop.add_callback(handle_response)

    try:
        loop.start()
    except KeyboardInterrupt:
        loop.stop()
