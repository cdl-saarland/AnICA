""" TODO document"""

import json
import os
from pathlib import Path
import textwrap

def load_json_config(path):
    """ Load a config dict in json format from the given path.

    Fields that end in `_path` and that specify a relative path starting with a
    '.' are made absolute by considering them relative to the directory of the
    given path.
    """
    if path is None:
        return dict()

    path = Path(path)

    with open(path, 'r') as f:
        json_dict = json.load(f)

    basepath = path.parent.resolve()
    res = _make_paths_absolute(basepath, json_dict)

    return res

def _make_paths_absolute(basepath, obj):
    """ Recursive helper method for `load_json_config`, to make paths absolute.
    """
    if isinstance(obj, dict):
        res = dict()
        for key, value in obj.items():
            new_value = None
            if key.endswith('_path') and isinstance(value, str):
                path = Path(value)
                if value.startswith('.'):
                    path = basepath.joinpath(path)
                new_value = str(path)
            else:
                new_value = _make_paths_absolute(basepath, value)
            res[key] = new_value
        return res
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(( _make_paths_absolute(basepath, x) for x in obj))
    else:
        return obj

def store_json_config(json_dict, path):
    """ Store the given dict as a pretty json file at the location specified by
    `path`. Path fields whose key ends with `_path` are made relative to
    `path`.
    """

    path = Path(path)

    basepath = path.parent.resolve()
    res = _make_paths_relative(basepath, json_dict)

    with open(path, 'w') as f:
        f.write(pretty_print(res))


def _make_paths_relative(basepath, obj):
    """ Recursive helper method for `store_json_config`, to make paths
    relative.
    """
    if isinstance(obj, dict):
        res = dict()
        for key, value in obj.items():
            new_value = None
            if key.endswith('_path') and isinstance(value, str):
                path = Path(value)
                path = path.resolve()
                path = os.path.relpath(path, start=basepath)
                new_value = str(path)
                if not new_value[0] == '.':
                    new_value = './' + new_value
            else:
                new_value = _make_paths_relative(basepath, value)
            res[key] = new_value
        return res
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(( _make_paths_relative(basepath, x) for x in obj))
    else:
        return obj


def pretty_print(obj, filter_doc=False):
    """ A prettier alternative to just json-dumping a config dict.
    If filter_doc is True, keys that are considered documentation (because of
    their suffix) are omitted.
    """
    json_str = json.dumps(obj)
    if len(json_str) <= 80:
        return json_str

    if isinstance(obj, dict):

        entries = []
        for key, value in obj.items():
            if filter_doc and any(map(lambda suffix: key.endswith(suffix), ConfigurableImpl._comment_suffixes)):
                continue

            value_str = pretty_print(value, filter_doc=filter_doc)
            lines = value_str.split('\n')
            if len(lines) > 1:
                value_str = lines[0] + "\n" + 4*" " + ("\n" + 4*" ").join(lines[1:])
            entries.append(f'  {json.dumps(key)}: ' + value_str )

        res = "{\n"
        res += ",\n".join(entries)
        res += "\n}"
        return res
    elif isinstance(obj, list) or isinstance(obj, tuple):
        entries = []
        for value in obj:
            value_str = pretty_print(value, filter_doc=filter_doc)
            entries.append(textwrap.indent(value_str, '  '))
        res = "[\n"
        res += ",\n".join(entries)
        res += "\n]"
        return res
    else:
        return json_str


class ConfigError(Exception):
    """ An error indicating that something went wrong in the DeviDisc
    configuration.
    """
    pass

class ConfigurableImpl:
    """ Parent class that is mixed in for classes with ConfigMeta as metaclass.

    It provides several methods to access the config data:
      - the instance method `configure` to set the data (the subclass should
        call this early, probably in its constructor)
      - the instance method `get_config` to get a json-printable dictionary
        containing the current config
      - the class method `get_default_config` to get a json-printable
        dictionary containing the default configuration for the class
    """

    _comment_suffixes = ['.doc', '.comment', '.info', '.c']

    def configure(self, partial_config):
        """ Use the specified config to initialize the fields specified as
        config_options in the subclass.

        Unspecified fields are taken from the default config.

        Throws a ConfigError if the given config contains an unknown entry.
        """
        for key in partial_config.keys():
            if key not in self._config_defaults.keys():
                if any(map(lambda suffix: key.endswith(suffix), self._comment_suffixes)):
                    continue
                raise ConfigError(
                        "Unknown config key for configurable class '{}': '{}'".format(
                            self.__class__.__name__, key))
        for key, default_val in self._config_defaults.items():
            val = partial_config.get(key, default_val)
            setattr(self, key, val)

    def get_config(self):
        """ Produce a json-printable dictionary containing the config of this
        object.

        Using this in `configure` should reproduce the current config options.
        """
        res = dict()
        for key in self._config_defaults.keys():
            res[key] = getattr(self, key)
            res[f'{key}.doc'] = self._config_docs[key]
        return res

    @classmethod
    def get_default_config(cls):
        """ Produce a json-printable dictionary containing the default config
        of this object.
        """
        res = dict()
        for key, val in cls._config_defaults.items():
            res[key] = val
            res[f'{key}.doc'] = cls._config_docs[key]
        return res


class ConfigMeta(type):
    """ Meta class to use for classes whose instances should contain
    reproducably configurable options.

    Classes that specify this metaclass need a `config_options` class attribute
    that contains a dictionary mapping options to tuples of default values and
    an explanatory comment in their definition.
    They should also call self.configure(config) with a suitable config
    dictionary in their __init__ method.

    In practice, this is less horrible than it sounds, consider the following
    example:
    ```
    class Foo(metaclass=ConfigMeta):
        config_options = dict(
            bar = (42, 'an important field')
        )
        def __init__(self, config):
            self.configure(config)

    foo1 = Foo({})
    foo2 = Foo({"bar": 47})
    foo3 = Foo({"baz": 47}) # raises a ConfigError, because `baz` is not a valid option

    print(foo1.bar) # 42
    print(foo2.bar) # 47
    print(foo2.get_config()) # a dictionary configuring bar to 47
    print(Foo.get_default_config()) # a dictionary configuring bar to 42
    ```
    """

    def __new__(cls, class_name, parents, attrs):
        assert 'config_options' in attrs,\
            "Implementations of the Configurable MetaClass need a 'config_options' class attribute!"

        opts = attrs['config_options']

        assert isinstance(opts, dict), "'config_options' needs to be a dict!"

        defaults = dict()
        docs = dict()
        for key, (val, doc) in opts.items():
            defaults[key] = val
            docs[key] = doc

        del attrs['config_options'] # clean up

        res = type.__new__(cls, class_name, parents + (ConfigurableImpl,), attrs)

        res._config_defaults = defaults
        res._config_docs = docs

        return res


