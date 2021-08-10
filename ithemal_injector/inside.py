#!/usr/bin/env python3

"""TODO document"""


import os
from pathlib import Path
import re
import subprocess

import rpyc
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer


def run_experiment(byte_str):
    bmk_file_name = "/home/ithemal/current_bmk.o"
    command = [
        "python", "/home/ithemal/ithemal/learning/pytorch/ithemal/predict.py",
        "--model", "/home/ithemal/ithemal/skylake/predictor.dump", # TODO make configurable
        "--model-data", "/home/ithemal/ithemal/skylake/trained.mdl", # TODO make configurable
        "--file", bmk_file_name,
        ]

    with open(bmk_file_name, 'wb') as f:
        f.write(byte_str)

    rv = subprocess.run(command, stdout=subprocess.PIPE)

    if rv.returncode != 0:
        print('  execution failed!')
        return { 'TP': None, 'error_cause': "execution failed" }

    str_res = rv.stdout.decode("utf-8")

    m = re.search(r"(\d+\.\d+)", str_res)
    if m is None:
        return { 'TP': None, 'error_cause': "throughput missing in ithemal output" }

    total_cycles = float(m.group(1))
    total_cycles = total_cycles / 100.0
    return {'TP': total_cycles}

class MyService(rpyc.Service):
    def __init__(self):
        pass

    def on_connect(self, conn):
        print("Opened connection")

    def on_disconnect(self, conn):
        print("Closed connection")

    def exposed_run_ithemal(self, byte_str):
        print("handling request for running ithemal ")
        res = run_experiment(byte_str)
        return res

def create_certs(self, sslpath='./ssl/'):
    """Create a self-signed certificate without password that is valid for
    (roughly) 10 years.
    """

    sslpath = Path(sslpath)

    os.makedirs(sslpath)

    subprocess.call([
            'openssl',
            'req',
            '-new',
            '-x509',
            '-days', '3650',
            '-nodes',
            '-out', sslpath / 'cert.pem',
            '-keyout', sslpath / 'key.pem',
        ])
    with open(sslpath / 'ca_certs.pem', 'w') as f:
        f.write('#TODO fill this\n\n')

def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('-p', '--port', metavar='PORT', type=int, default="42010",
                      help='the port to listen for requests')
    ap.add_argument('--sslpath', metavar='PATH', default="./ssl/",
                      help='the path to a folder containing an SSL key, certificate and ca file')
    args = ap.parse_args()

    sslpath = Path(args.sslpath)

    if not sslpath.is_dir():
        create_certs(sslpath)

    certfile = sslpath / "cert.pem"
    keyfile = sslpath / "key.pem"
    ca_certs = sslpath / "ca_certs.pem"

    for f in (certfile, keyfile, ca_certs):
        if not f.is_file():
            raise RuntimeError("SSL file missing: {}".format(f))

    authenticator = SSLAuthenticator(keyfile=keyfile, certfile=certfile, ca_certs=ca_certs)

    service = MyService()

    t = ThreadedServer(service, port=args.port, authenticator=authenticator)
    print("Starting server")
    t.start()


if __name__ == '__main__':
    main()

