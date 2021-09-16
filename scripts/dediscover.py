#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

import argparse
from datetime import datetime
import math
from pathlib import Path
import random
import os
import sys

from iwho.utils import init_logging, update_logfile

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import load_json_config, store_json_config
import devidisc.discovery as discovery


import logging
logger = logging.getLogger(__name__)


def main():
    HERE = Path(__file__).parent

    default_campaign_config = HERE.parent / "configs" / "campaigns" / "campconfig_01.json"
    default_seed = 424242


    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', default=default_campaign_config, metavar="CONFIG",
            help='campaign configuration file in json format')

    argparser.add_argument('--loop', action='store_true', help='if set, loop through the campaign config indefinitely')

    argparser.add_argument('--check-config', action='store_true', help='if set, do not do any real discovery, only check that the configuration is plausible')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('outdir', metavar="OUTDIR",
            help='output directory for reports and results')

    args = argparser.parse_args()

    check_config = args.check_config

    random.seed(args.seed)

    campaign_config = load_json_config(args.config)

    outdir = Path(args.outdir).resolve()

    init_logging('info')

    if check_config:
        total_seconds = 0

    while True:
        for idx, config in enumerate(campaign_config):
            # create a campaign directory
            timestamp = datetime.now().replace(microsecond=0).isoformat()
            curr_out_dir = outdir / f'campaign_{idx:03d}_{timestamp}'
            os.makedirs(curr_out_dir)

            update_logfile(logfile=curr_out_dir / 'log.txt')

            actx_config = load_json_config(config['abstraction_config_path'])
            termination_criterion = config['termination']
            predictor_keys = config['predictors']

            # set the db path
            actx_config['measurement_db'] = {"db_path": str(curr_out_dir / 'measurements.db')}

            actx = AbstractionContext(config=actx_config)
            actx.predmanager.set_predictors(predictor_keys)

            outdict = {**config, "abstraction_config": actx.get_config()}
            store_json_config(outdict, curr_out_dir / 'campaign_config.json')

            # initialize the measurement db
            with actx.measurement_db as mdb:
                mdb.create_tables()

            if check_config:
                termination = termination_criterion
                if any(map(lambda x: x in termination.keys(), ['days', 'hours', 'minutes', 'seconds'])):
                    max_seconds_passed = termination.get('days', 0) * 3600 * 24
                    max_seconds_passed += termination.get('hours', 0) * 3600
                    max_seconds_passed += termination.get('minutes', 0) * 60
                    max_seconds_passed += termination.get('seconds', 0)
                    total_seconds += max_seconds_passed
                else:
                    total_seconds = math.inf
                continue

            discoveries = discovery.discover(actx, termination=termination_criterion, out_dir=curr_out_dir)

            # TODO store those

        if (not args.loop):
            break

    if check_config:
        days = total_seconds // (3600 * 24)
        total_seconds %= 3600 * 24
        hours = total_seconds // 3600
        total_seconds %= 3600
        minutes = total_seconds // 60
        total_seconds %= 60
        seconds = total_seconds
        print(f"estimated total time: {days} days, {hours} hours, {minutes} minutes, {seconds} seconds")




if __name__ == "__main__":
    main()
