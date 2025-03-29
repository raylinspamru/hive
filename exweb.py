import os
from datetime import datetime

def collect_project_code(output_file="project_code.txt"):
    # Список папок для поиска файлов
    directories = [
        "static/js",    # для .js файлов
        "web",          # для .py файлов
        "utils",        # для .py файлов
        "templates"     # для .html файлов
    ]
    
    # Папки для игнорирования
    ignore_dirs = {"venv", "__pycache__"}
    
    # Расширения файлов и их соответствующие папки
    file_extensions = {
        ".py": ["web", "utils", ""],  # "" для main.py в корне
        ".html": ["templates"],
        ".js": ["static/js"],
        ".txt": ["static/js", "web", "utils", "templates"]
    }
    
    # Открываем файл для записи
    with open(output_file, "w", encoding="utf-8") as outfile:
        # Записываем заголовок с датой
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        outfile.write(f"Project Code Collection - Generated on {current_date}\n")
        outfile.write("=" * 50 + "\n\n")
        
        # Сначала обработаем main.py в корневой директории
        if os.path.exists("main.py"):
            outfile.write("File: main.py\n")
            outfile.write("-" * 50 + "\n")
            with open("main.py", "r", encoding="utf-8") as f:
                outfile.write(f.read())
            outfile.write("\n" + "=" * 50 + "\n\n")
        
        # Обработка всех указанных директорий
        for directory in directories:
            if not os.path.exists(directory):
                continue
                
            for root, dirs, files in os.walk(directory):
                # Исключаем игнорируемые директории
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                
                for file in sorted(files):  # Сортируем файлы для порядка
                    # Проверяем расширение файла
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in file_extensions:
                        # Проверяем, соответствует ли директория расширению
                        if directory in file_extensions[file_ext] or "" in file_extensions[file_ext]:
                            file_path = os.path.join(root, file)
                            relative_path = os.path.relpath(file_path)
                            
                            # Пропускаем файлы из игнорируемых директорий
                            if any(ignore_dir in relative_path.split(os.sep) for ignore_dir in ignore_dirs):
                                continue
                            
                            # Записываем информацию о файле
                            outfile.write(f"File: {relative_path}\n")
                            outfile.write("-" * 50 + "\n")
                            
                            # Читаем и записываем содержимое файла
                            try:
                                with open(file_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    outfile.write(content)
                            except Exception as e:
                                outfile.write(f"Error reading file: {str(e)}\n")
                            
                            outfile.write("\n" + "=" * 50 + "\n\n")

def main():
    try:
        collect_project_code()
        print("Код проекта успешно собран в файл project_code.txt")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    main()