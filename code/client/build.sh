pyinstaller --name "RoboMaster校内赛选手端" --onefile --noconsole --icon=assets/logo.png --add-data "assets;assets" --additional-hooks-dir=hooks main.py

pyinstaller --name "RoboMaster校内赛选手端" --onefile --icon=assets/logo.png --add-data "assets;assets" --additional-hooks-dir=hooks main.py
