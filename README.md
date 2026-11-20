Пока это попытка запустить Windows-вайбкодинг под мак

Установка на macOS через Homebrew:

$ brew install git uv python-tk
$ git clone https://github.com/hcdrunk/HcdLapseStudio
$ cd HcdLapseStudio
$ uv python install 3.13
$ uv venv --clear --python 3.13
$ uv pip install -r requirements.txt
$ uv run timelapse_app.py
