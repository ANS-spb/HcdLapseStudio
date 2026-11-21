*Установка на Windows:*

Скачайте и запустите EXE со страницы релизов: \
https://github.com/hcdrunk/HcdLapseStudio/releases

Установка на macOS через [Homebrew](https://brew.sh):

```bash
brew install git uv python-tk \
git clone https://github.com/hcdrunk/HcdLapseStudio \
cd HcdLapseStudio \
uv python install 3.13 \
uv venv --clear --python 3.13 \ 
uv pip install -r requirements.txt \ 
uv run timelapse_app.py \ 
```
