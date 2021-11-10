#!/bin/bash

set -ex

ARCHIVENAME=maqao.intel64.2.14.1

wget http://www.maqao.org/release/${ARCHIVENAME}.tar.xz

tar -xf ${ARCHIVENAME}.tar.xz

mv ${ARCHIVENAME} maqao

