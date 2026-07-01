pyinstaller --name "RoboMaster校内赛裁判端" --onefile --noconsole --icon=assets/logo.png --add-data "assets;assets" --additional-hooks-dir=hooks main.py

pyinstaller --name "RoboMaster校内赛裁判端" --onefile --icon=assets/logo.png --add-data "assets;assets" --additional-hooks-dir=hooks main.py
