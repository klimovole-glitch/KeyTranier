# Выпуск версии 1.0.0

Все команды выполняются в терминале VS Code (**Terminal → New Terminal**)
в папке проекта `KeyTrainer`.

## 1. Получить свежий develop
```powershell
git checkout develop
git pull
```

## 2. Проверить проект
```powershell
py -m pip install -r requirements-dev.txt
py -m black --check .
py -m flake8
py -m pytest
py -m keytrainer
```
Тесты должны пройти, программа — открыться.

## 3. Создать ветку релиза и поднять версию
```powershell
git checkout -b release/1.0.0
```
Поменять `0.1.0` на `1.0.0` в двух файлах:
- `pyproject.toml` — строка `version = "0.1.0"`;
- `keytrainer/__init__.py` — строка `__version__ = "0.1.0"`.

```powershell
git add pyproject.toml keytrainer/__init__.py
git commit -m "chore(release): version 1.0.0"
git push -u origin release/1.0.0
```

## 4. Pull Request в main и code review
1. GitHub → **Pull requests → New pull request**: `base: main` ← `compare: release/1.0.0`.
2. Название: «Релиз 1.0.0». В описание вставить раздел `[1.0.0]` из `CHANGELOG.md`.
3. Справа **Reviewers** — добавить одногруппника. Его замечания записать в `docs/code_review.md`,
   исправления закоммитить в ту же ветку `release/1.0.0`.
4. **Merge pull request** → **Confirm merge**.
5. Вернуть изменения версии в develop: ещё один PR `base: develop` ← `compare: main` → Merge.

## 5. Собрать KeyTrainer.exe
```powershell
git checkout main
git pull
py -m PyInstaller keytrainer.spec
```
Файл появится в `dist\KeyTrainer.exe`. Запустить его двойным щелчком и проверить.

## 6. Опубликовать релиз
1. GitHub → справа **Releases → Create a new release** (или **Draft a new release**).
2. **Choose a tag** → ввести `v1.0.0` → **Create new tag**; **Target** — `main`.
3. Заголовок: `KeyTrainer Analytics 1.0.0`. Описание — раздел `[1.0.0]` из `CHANGELOG.md`.
4. Перетащить `dist\KeyTrainer.exe` в поле **Attach binaries**.
5. **Publish release**.
