import os
import subprocess
import sys

def perform_update_and_restart():
    """
    Выполняет git pull с GitHub и перезапускает процесс бота.
    Локальные файлы loyalty.db и .env не затрагиваются, если они добавлены в .gitignore.
    """
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    try:
        subprocess.run(["git", "pull"], cwd=repo_dir, check=True)
    except Exception as e:
        print(f"⚠️ Ошибка при выполнении git pull: {e}")
    
    print("🔄 Обновление завершено. Перезапуск процесса бота...")
    python = sys.executable
    os.execl(python, python, *sys.argv)
