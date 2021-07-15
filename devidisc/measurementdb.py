from datetime import datetime
import sqlite3

from .configurable import ConfigMeta

class MeasurementDB(metaclass=ConfigMeta):
    """TODO document"""
    config_options = dict(
        db_name = ('measurements.db',
            'path and file name of the sqlite3 database to use'),
    )

    def __init__(self, config):
        self.configure(config)

        self.con = None
        self.nesting_level = 0 # for making the ContextManager re-entrant

    def _init_con(self):
        self.con = sqlite3.connect(self.db_name)
        self.con.row_factory = sqlite3.Row

    def _deinit_con(self):
        self.con.close()
        self.con = None

    def __enter__(self):
        if self.nesting_level == 0:
            self._init_con()
        self.nesting_level += 1
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.nesting_level -= 1
        if self.nesting_level == 0:
            self._deinit_con()

    def get_series(self, series_id):
        con = self.con
        assert con is not None
        cur = con.cursor()

        series_dict = dict(series_id=series_id)

        cur.execute("SELECT source_computer, timestamp FROM series WHERE series_id=?", (series_id,))
        result = cur.fetchone()

        series_dict["series_date"] = datetime.fromtimestamp(result["timestamp"]).isoformat()
        series_dict["source_computer"] = result["source_computer"]

        predictor_cache = dict()
        cur.execute("SELECT predictor_id, toolname, version FROM predictors")
        for r in cur.fetchall():
            predictor_cache[r["predictor_id"]] = (r["toolname"], r["version"])

        uarch_cache = dict()
        cur.execute("SELECT uarch_id, uarch_name FROM uarchs")
        for r in cur.fetchall():
            uarch_cache[r["uarch_id"]] = r["uarch_name"]

        measurements = []

        cur.execute("SELECT measurement_id, input FROM measurements WHERE series_id=?", (series_id,))
        for r in cur.fetchall():
            meas_id = r['measurement_id']
            meas_dict = dict(measurement_id=meas_id)
            meas_dict["input"] = r['input']

            pred_runs = []

            cur.execute("SELECT predictor_id, uarch_id, result, remark FROM predictor_runs WHERE measurement_id=?", (meas_id,))
            for r in cur.fetchall():
                pred_run = dict()
                pred_run["result"] = r["result"]
                pred_run["remark"] = r["remark"]
                pred_run["predictor"] = predictor_cache[r["predictor_id"]]
                pred_run["uarch"] = uarch_cache[r["uarch_id"]]
                pred_runs.append(pred_run)

            meas_dict["predictor_runs"] = pred_runs

            measurements.append(meas_dict)

        series_dict["measurements"] = measurements
        return series_dict

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

