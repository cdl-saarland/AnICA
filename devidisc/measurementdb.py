from datetime import datetime
import sqlite3

class MeasurementDB:
    """TODO document"""
    def __init__(self, db_name):
        self.db_name = db_name
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
        # TODO


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

