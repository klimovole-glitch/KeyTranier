# KeyTrainer Analytics — клавиатурный тренажер с аналитикой

Десктопное приложение для обучения слепой печати: генерация упражнений в пяти режимах,
метрики WPM / CPM / процент ошибок, тепловая карта клавиатуры, история и профили.

## Технологии
Python 3.10+, Tkinter, SQLite (`sqlite3`), matplotlib, pytest, Poetry, PyInstaller,
black + flake8 (pre-commit).

## Архитектура
Многослойная архитектура, паттерны MVC и Repository:

```
keytrainer/
  config.py          пути (pathlib), логирование
  data/              слой доступа к данным
    schema.sql       схема БД (7 таблиц, 3NF)
    database.py      подключение, транзакции, резервная копия, восстановление
    seed.py          заполнение справочников из resources/
    repositories/    CRUD для каждой таблицы, только параметризованные запросы
    demo_data.py     генератор тестовых сессий
  resources/         словари (≥1000 слов на язык) и тексты
tests/               pytest
```

## Установка и запуск
```bash
poetry install
poetry run pre-commit install
poetry run python -m keytrainer                                   # создать БД
poetry run python -m keytrainer.data.demo_data --user Тест --sessions 20
```
В Linux для Tkinter нужен пакет `python3-tk`.

## Проверка качества
```bash
poetry run black .
poetry run flake8
poetry run pytest
```
