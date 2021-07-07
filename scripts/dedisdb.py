#!/usr/bin/env python3

""" A simple script to manage the discovery database for the deviation
discovery.
"""

from pathlib import Path
import os
import sqlite3
import sys
import json
from datetime import datetime

class MeasurementDB:
    def __init__(self, db_name):
        self.db_name = db_name
        self.con = None

    def _init_con(self):
        self.con = sqlite3.connect(self.db_name)
        self.con.row_factory = sqlite3.Row

    def _deinit_con(self):
        self.con.close()
        self.con = None

    def __enter__(self):
        self._init_con()
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self._deinit_con()


    def create_tables(self):
        con = self.con
        assert con is not None

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
                series_id INTEGER NOT NULL,
                input TEXT NOT NULL
            )""")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictor_runs (
                predrun_id INTEGER NOT NULL PRIMARY KEY,
                measurement_id INTEGER NOT NULL,
                predictor_id INTEGER NOT NULL,
                uarch_id INTEGER NOT NULL,
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


    def add_series(self, measdict):
        # {
        #   "series_date": $date,
        #   "source_computer": "skylake",
        #   "measurements": [{
        #       "input": "49ffabcdef",
        #       "predictor_runs": [{
        #           "predictor": ["llvm-mca", "12.0"],
        #           "uarch": "SKL",
        #           "result": 42.17,
        #           "remark": null
        #       }]
        #   }]
        # }

        con = self.con
        assert con is not None

        series_date = measdict["series_date"]
        timestamp = round(datetime.fromisoformat(series_date).timestamp())

        source_computer = measdict["source_computer"]

        cur = con.cursor()

        # add a new series
        cur.execute("INSERT INTO series VALUES (NULL, ?, ?)", (source_computer, timestamp))
        series_id = cur.lastrowid

        predictor_ids = dict()
        uarch_ids = dict()

        for m in measdict["measurements"]:
            inp = m["input"]

            cur.execute("INSERT INTO measurements VALUES (NULL, ?, ?)", (series_id, inp))
            measurement_id = cur.lastrowid

            predictor_runs = m["predictor_runs"]

            for r in predictor_runs:
                predictor = tuple(r["predictor"])
                uarch = r["uarch"]

                res = r.get("result", None)
                remark = r.get("remark", None)

                predictor_id = predictor_ids.get(predictor, None)
                if predictor_id is None:
                    toolname, version = predictor
                    cur.execute("SELECT predictor_id FROM predictors WHERE toolname=? and version=?", (toolname, version))
                    result = cur.fetchone()
                    if result is None:
                        cur.execute("INSERT INTO predictors VALUES (NULL, ?, ?)", (toolname, version))
                        predictor_id = cur.lastrowid
                    else:
                        predictor_id = result['predictor_id']

                    predictor_ids[predictor] = predictor_id

                # it would be nicer to deduplicate this with the predictor code
                uarch_id = uarch_ids.get(uarch, None)
                if uarch_id is None:
                    cur.execute("SELECT uarch_id FROM uarchs WHERE uarch_name=?", (uarch,))
                    result = cur.fetchone()
                    if result is None:
                        cur.execute("INSERT INTO uarchs VALUES (NULL, ?)", (uarch,))
                        uarch_id = cur.lastrowid
                    else:
                        uarch_id = result['uarch_id']

                    uarch_ids[uarch] = uarch_id

                cur.execute("INSERT INTO predictor_runs VALUES (NULL, ?, ?, ?, ?, ?)", (measurement_id, predictor_id, uarch_id, res, remark))

        con.commit()

        return series_id



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
        return 1


    with MeasurementDB(db_name) as dbman:
        if args.create:
            dbman.create_tables()
        elif args.measurements is not None:
            meas_path = Path(args.measurements)
            if os.path.isdir(meas_path):
                file_list = [ meas_path / f for f in os.listdir(meas_path) if f.endswith('.json')]
            elif os.path.isfile(meas_path):
                file_list = [ meas_path ]
            else:
                print("Error: Measurement file does not exist!", file=sys.stderr)
                return 1

            print(f"Importing data from {len(file_list)} measurement file(s)")
            total_num_added = 0
            for idx, path in enumerate(file_list):
                with open(path, 'r') as meas_file:
                    meas_dict = json.load(meas_file)
                dbman.add_series(meas_dict)
                num_added = len(meas_dict['measurements'])
                total_num_added += num_added
                print(f" {idx}: Successfully added {num_added} measurements in a new series.")
            print(f"Successfully added {total_num_added} measurements.")
        else:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
