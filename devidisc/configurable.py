""" TODO document"""


class ConfigError(Exception):
    pass

class Configurable:
    """ TODO document
    """
    def __init__(self, defaults, config={}):
        self._defaults = dict()
        self._docs = dict()
        for key, (val, doc) in defaults.items():
            self._defaults[key] = val
            self._docs[key] = doc
        self.set_config(config)

    _comment_suffixes = ['.doc', '.comment', '.info', '.c']

    def set_config(self, partial_config):
        for key in partial_config.keys():
            if key not in self._defaults.keys():
                if any(map(lambda suffix: key.endswith(suffix), self._comment_suffixes)):
                    continue
                raise ConfigError("Unknown config key for configurable class '{}': '{}'".format(self.__class__.__name__, key))
        for key, default_val in self._defaults.items():
            val = partial_config.get(key, default_val)
            setattr(self, key, val)

    def get_default_config(self):
        res = dict()
        for key, val in self._defaults.items():
            res[key] = val
            res[f'{key}.doc'] = self._docs[key]
        return self._defaults

