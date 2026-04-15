from __future__ import annotations

from plugins._skills.helpers.runtime import coerce_config


def get_plugin_config(default=None, **kwargs):
    return coerce_config(default)


def save_plugin_config(settings=None, **kwargs):
    return coerce_config(settings)
