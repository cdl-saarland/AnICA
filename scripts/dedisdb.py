#!/usr/bin/env python3

""" A simple script to manage the discovery database for the deviation
discovery.
"""

import json
import os
from pathlib import Path
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.measurementdb import MeasurementDB

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


    with MeasurementDB({"db_name": db_name}) as dbman:
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
