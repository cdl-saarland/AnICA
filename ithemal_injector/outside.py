#!/usr/bin/env python3

"""TODO document"""

from pathlib import Path

import rpyc

class RemoteLink:
    def __init__(self, hostname, port, sslpath, request_timeout):
        sslpath = Path(sslpath)
        self.hostname = hostname
        self.port = port
        self.certfile = str(sslpath / "cert.pem")
        self.keyfile = str(sslpath / "key.pem")
        self.request_timeout = request_timeout

        self.conn = None

    def __enter__(self):
        self.conn = rpyc.ssl_connect(self.hostname,
                port=self.port,
                keyfile=self.keyfile,
                certfile=self.certfile,
                config={'sync_request_timeout': self.request_timeout},
                )
        return self

    def __exit__(self, exc_info, exc_value, trace):
        self.conn.close()
        return

    def run_ithemal(self, byte_str):
        assert self.conn is not None, "Connection must be open!"
        try:
            return self.conn.root.run_ithemal(byte_str)
        except rpyc.AsyncResultTimeout:
            return None


def main():
    import argparse

    rl = RemoteLink('127.0.0.1', port='42010', sslpath='./ssl', request_timeout=30)


    with open("../iaca_input.o", 'rb') as f:
        instr = f.read()

    with rl:
        print(rl.run_ithemal(instr))

if __name__ == '__main__':
    main()

