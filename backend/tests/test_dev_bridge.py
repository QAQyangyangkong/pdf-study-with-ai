import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DevBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            cls.port=sock.getsockname()[1]
        cls.token='test-dev-bridge-token-no-provider-key'
        cls.process=subprocess.Popen([sys.executable,'-m','studynote.main','--http',str(cls.port),'--data-dir',cls.temp.name],
            env={**os.environ,'STUDYNOTE_DEV_TOKEN':cls.token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.url=f'http://127.0.0.1:{cls.port}/ipc'
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            try:
                urlopen(cls.request(),timeout=1).close()
                return
            except URLError:
                time.sleep(.05)
        cls.process.terminate();cls.process.wait(timeout=5);cls.temp.cleanup()
        raise RuntimeError('Development bridge did not start')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=5);cls.temp.cleanup()

    @classmethod
    def request(cls,token=None,origin='http://127.0.0.1:1420'):
        body=json.dumps({'protocol_version':1,'id':'bridge','method':'workspace.get','params':{}}).encode()
        return Request(cls.url,data=body,headers={'Content-Type':'application/json','Origin':origin,
            'Authorization':'Bearer '+(cls.token if token is None else token)})

    def test_valid_token_and_origin_return_workspace_without_token(self):
        with urlopen(self.request(),timeout=3) as response:
            body=response.read().decode()
            self.assertEqual(response.headers['Access-Control-Allow-Origin'],'http://127.0.0.1:1420')
        self.assertTrue(json.loads(body)['ok'])
        self.assertNotIn(self.token,body)

    def test_wrong_token_and_foreign_origin_are_rejected(self):
        for request in [self.request(token='wrong'),self.request(origin='https://foreign.example')]:
            with self.assertRaises(HTTPError) as error:
                urlopen(request,timeout=3)
            self.assertEqual(error.exception.code,403)
            error.exception.close()
