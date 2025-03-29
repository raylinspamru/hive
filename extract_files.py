import os
from pathlib import Path

# Укажите корневую директорию проекта
ROOT_DIR = Path(__file__).parent

# Расширения файлов для обработки
VALID_EXTENSIONS = {'.py', '.txt', '.html'}

# Папки для игнорирования
IGNORE_DIRS = {'venv', '__pycache__'}

# Файлы для игнорирования
IGNORE_FILES = {'extract_files.py', 'project_code.txt'}

def extract_all_files_to_single_file(output_filename='project_code.txt'):
    output_path = ROOT_DIR / output_filename
    
    with open(output_path, 'w', encoding='utf-8') as output_file:
        # Записываем заголовок
        output_file.write("ПОЛНЫЙ КОД ПРОЕКТА\n")
        output_file.write("=" * 50 + "\n\n")
        
        # Рекурсивно обходим все папки и файлы
        for root, dirs, files in os.walk(ROOT_DIR):
            # Исключаем игнорируемые директории
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file_name in files:
                # Проверяем, не входит ли файл в список игнорируемых
                if file_name in IGNORE_FILES:
                    continue
                
                # Проверяем расширение файла
                file_ext = Path(file_name).suffix.lower()
                if file_ext not in VALID_EXTENSIONS:
                    continue
                
                # Формируем полный путь к файлу
                file_path = Path(root) / file_name
                # Получаем путь относительно корневой директории
                relative_path = file_path.relative_to(ROOT_DIR)
                
                # Записываем разделитель и информацию о файле
                output_file.write(f"{'=' * 50}\n")
                output_file.write(f"Файл: {relative_path}\n")
                output_file.write(f"{'=' * 50}\n\n")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as source_file:
                        content = source_file.read()
                        output_file.write(content)
                        # Добавляем перенос строки, если его нет
                        if not content.endswith('\n'):
                            output_file.write('\n')
                    print(f"Успешно обработан файл: {relative_path}")
                except Exception as e:
                    output_file.write(f"ОШИБКА: Не удалось прочитать файл: {str(e)}\n")
                    print(f"Ошибка при обработке {relative_path}: {str(e)}")
                
                output_file.write("\n")  # Дополнительный отступ между файлами

if __name__ == "__main__":
    print("Начало извлечения файлов...")
    extract_all_files_to_single_file()
    print(f"Извлечение завершено! Результат сохранен в 'project_code.txt'")