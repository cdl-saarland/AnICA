#!/usr/bin/env python3

""" A simple script to manage the discovery database for the deviation
discovery.
"""

import os
import sqlite3
import sys
import json
from datetime import datetime

def create_tables(con):
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictors (
            predictor_id INTEGER NOT NULL PRIMARY KEY,
            toolname TEXT NOT NULL,
            version TEXT NOT NULL,
            UNIQUE(toolname, version)
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS series (
            series_id INTEGER NOT NULL PRIMARY KEY,
            source_computer TEXT NOT NULL,
            timestamp INTEGER NOT NULL
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            measurement_id INTEGER NOT NULL PRIMARY KEY,
            predictor_id INTEGER NOT NULL,
            series_id INTEGER NOT NULL,
            uarch_id INTEGER NOT NULL,
            input TEXT NOT NULL,
            result REAL,
            remark TEXT
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS uarchs (
            uarch_id INTEGER NOT NULL PRIMARY KEY,
            uarch_name TEXT UNIQUE NOT NULL
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS discoveries (
            discovery_id INTEGER NOT NULL PRIMARY KEY,
            remark TEXT
        )""")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS witnesses (
            discovery_id INTEGER NOT NULL,
            measurement_id INTEGER NOT NULL,
            PRIMARY KEY (discovery_id, measurement_id)
        )""")
    con.commit()


def add_uarchs(con):
    cur = con.cursor()
    cur.execute("INSERT INTO uarchs VALUES (NULL, 'SKL')")
    con.commit()


def add_measurement_dict(con, measdict):
    # {
    #   "series_date": $date,
    #   "source_computer": "skylake",
    #   "measurements": [{
    #       "predictor": ["llvm-mca", "12.0"],
    #       "uarch": "SKL",
    #       "input": "49ffabcdef",
    #       "result": 42.17,
    #       "remark": null
    #   }]
    # }

    series_date = measdict["series_date"]
    timestamp = round(datetime.fromisoformat(series_date).timestamp())

    source_computer = measdict["source_computer"]

    cur = con.cursor()

    # add a new series
    cur.execute(f"INSERT INTO series VALUES (NULL, '{source_computer}', {timestamp})")
    series_id = cur.lastrowid

    predictor_ids = dict()
    uarch_ids = dict()

    for m in measdict["measurements"]:
        predictor = tuple(m["predictor"])
        uarch = m["uarch"]

        inp = m["input"]
        res = m.get("result", None)
        if res is None:
            res = "NULL"
        remark = m.get("remark", None)
        if remark is None:
            remark = "NULL"
        else:
            remark = f"'{remark}'"

        predictor_id = predictor_ids.get(predictor, None)

        if predictor_id is None:
            toolname = predictor[0]
            version = predictor[1]
            cur.execute(f"SELECT predictor_id FROM predictors WHERE toolname='{toolname}' and version='{version}'")
            result = cur.fetchone()
            if result is None:
                cur.execute(f"INSERT INTO predictors VALUES (NULL, '{toolname}', '{version}')")
                predictor_id = cur.lastrowid
            else:
                predictor_id = result['predictor_id']

            predictor_ids[predictor] = predictor_id

        # TODO this is code duplication!
        uarch_id = uarch_ids.get(uarch, None)

        if uarch_id is None:
            cur.execute(f"SELECT uarch_id FROM uarchs WHERE uarch_name='{uarch}'")
            result = cur.fetchone()
            if result is None:
                cur.execute(f"INSERT INTO uarchs VALUES (NULL, '{uarch}')")
                uarch_id = cur.lastrowid
            else:
                uarch_id = result['uarch_id']

            uarch_ids[uarch] = uarch_id

        cur.execute(f"INSERT INTO measurements VALUES (NULL, {predictor_id}, {series_id}, {uarch_id}, '{inp}', {res}, {remark})")
    con.commit()
    return len(measdict["measurements"])


def main():
    import argparse

    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument('dbfile', metavar="DB_FILE", help='path of a database to work with')
    argparser.add_argument('-c', '--create', action='store_true', help='create and initialize the database at the specified path')
    argparser.add_argument('-m', '--measurements', default=None, help='add the specified measurements in json format to the database')
    args = argparser.parse_args()

    # --export
    # --import

    db_name = args.dbfile

    db_exists = os.path.isfile(db_name)

    if db_exists and args.create:
        print("Error: Trying to create a database that already exists!", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(db_name)

    if args.create:
        create_tables(con)
        add_uarchs(con)
    elif args.measurements is not None:
        if not os.path.isfile(args.measurements):
            print("Error: Measurement file does not exist!", file=sys.stderr)
            sys.exit(1)
        with open(args.measurements, 'r') as meas_file:
            meas_dict = json.load(meas_file)
        num_added = add_measurement_dict(con, meas_dict)
        print(f"Successfully added {num_added} measurements in a new series.")
    else:
        pass

    con.close()

if __name__ == "__main__":
    main()
