""" Helpers to generate a configuration environment with default configs for
all relevant components.
"""

import os
from pathlib import Path
from shutil import copy

from anica.abstractioncontext import AbstractionContext
from iwho.configurable import store_json_config

def gen_configs(dest_dir):
    """ Insert a directory struture with config example files for all
    AnICA components to the `dest_dir` directory.
    """
    dest_dir = Path(dest_dir)

    here_dir = Path(__file__).parent
    template_dir = here_dir / 'inputfiles' / 'configs'

    predictors_cfg_dir = dest_dir / 'configs'/ 'predictors'
    abstraction_cfg_dir = dest_dir / 'configs'/ 'abstraction'
    campaign_cfg_dir = dest_dir / 'configs'/ 'campaign'


    os.makedirs(predictors_cfg_dir)
    copy(src=template_dir / 'pred_registry_template.json', dst=predictors_cfg_dir / 'pred_registry_template.json')
    copy(src=template_dir / 'pred_registry_default.json', dst=predictors_cfg_dir / 'pred_registry.json')
    os.makedirs(predictors_cfg_dir / 'filters')


    os.makedirs(abstraction_cfg_dir)
    default_cfg = AbstractionContext.get_default_config()
    default_cfg['predmanager']['registry_path'] = str((predictors_cfg_dir / 'pred_registry.json').absolute())
    default_cfg['measurement_db'] = None
    store_json_config(default_cfg, abstraction_cfg_dir / 'default.json')


    os.makedirs(campaign_cfg_dir)
    copy(src=template_dir / 'campaign_simple.json', dst=campaign_cfg_dir / 'simple.json')
    copy(src=template_dir / 'campaign_templated.json', dst=campaign_cfg_dir / 'templated.json')


    os.makedirs(dest_dir / 'results')
