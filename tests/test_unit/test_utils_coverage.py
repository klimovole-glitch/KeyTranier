import pytest
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def test_config_imports():
    '''Проверка, что config импортируется и пути заданы.'''
    from keytrainer import config
    assert config.APP_NAME is not None
    assert config.DB_PATH is not None
    assert config.SETTINGS_PATH is not None

def test_labels_imports():
    '''Проверка, что labels импортируются.'''
    from keytrainer import labels
    assert labels.LAYOUT_TITLES is not None

def test_utils_imports():
    '''Проверка, что utils импортируются.'''
    from keytrainer.utils import text_files
    assert text_files is not None

def test_read_text_file():
    '''Проверка чтения TXT-файла (если есть).'''
    from keytrainer.utils import text_files
    # Создаем временный файл для проверки
    test_file = Path('test_temp.txt')
    test_file.write_text('Привет, мир!', encoding='utf-8')
    try:
        content = test_file.read_text(encoding='utf-8')
        assert 'Привет' in content
    finally:
        if test_file.exists():
            test_file.unlink()

def test_pathlib_usage():
    '''Проверка, что пути работают.'''
    p = Path('.')
    assert p.is_dir()
