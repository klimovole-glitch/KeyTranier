# Configuration file for the Sphinx documentation builder.
#
# Полный список параметров конфигурации и документацию можно найти по адресу:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Добавляем корневую папку проекта в системный путь, чтобы Sphinx мог находить пакет keytrainer
sys.path.insert(0, os.path.abspath('../../'))

# -- Информация о проекте -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'KeyTranier'
copyright = '2026, Климов О.В.'
author = 'Климов О.В.'
release = '1.0'

# -- Общая конфигурация ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Подключаем расширения для автоматической генерации документации из docstrings Python-кода
extensions = [
    'sphinx.ext.autodoc',     # Автоматическое документирование модулей и классов
    'sphinx.ext.napoleon',    # Поддержка docstrings в стиле Google и NumPy
    'sphinx.ext.viewcode',    # Добавление ссылок на исходный код в документации
]

templates_path = ['_templates']
exclude_patterns = []

language = 'ru'

# -- Параметры для вывода HTML -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Используем удобную официальную тему ReadTheDocs
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']