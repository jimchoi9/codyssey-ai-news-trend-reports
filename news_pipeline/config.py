"""Configuration paths are relative to the configuration file, not the shell cwd."""
import json
import logging
import math
import os
from pathlib import Path


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding='utf-8'))
    for key, default in [('database', 'data/news.db'), ('output_dir', 'output'), ('log_file', 'logs/news.log')]:
        config[key] = str((path.parent / config.get(key, default)).resolve())
    if config.get('duplicate_policy', 'skip') not in ('skip', 'upsert'):
        raise ValueError('duplicate_policy는 skip 또는 upsert여야 합니다.')
    for key, default, allow_zero in [('request_timeout', 20, False), ('request_delay', 1, True)]:
        value = float(config.get(key, default))
        if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
            raise ValueError(f'{key} 값이 올바르지 않습니다.')
        config[key] = value
    if config.get('font_path'):
        config['font_path'] = str((path.parent / config['font_path']).resolve())
    ai = config.setdefault('ai', {})
    ai['api_key'] = os.environ.get(ai.get('api_key_env', 'OPENAI_API_KEY')) or ai.get('api_key', '')
    return config


def configure_logging(config):
    path = Path(config['log_file'])
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(path, encoding='utf-8')], force=True)
