"""
The script is written by Ivan Kulikov

Данный скрипт позволяет производить бэкап репозиториев с github на локальный носитель информации.
Есть следующие варианты бэкапа:
- все репозитории из профиля пользователя
- все репозитории из организации (к которым у пользователя есть доступ)

Логика работы:
Если репозитория в папке для загрузки нет, то репозиторий будет склонирован.
Если репозиторий уже был склонирован ранее, производится выполнение команд:
1. git fetch --all --prune
    Используется для обновления всех удаленных репозиториев, связанных с вашим локальным репозиторием, 
    и удаления ссылок на удаленные ветки, которые больше не существуют в удаленных репозиториях
2. Определяет название главной ветки после клонирования репозитория,
    подразумевается что ветка будет названа как "main" ЛИБО "master" (Если название ветки другое, произойдет ошибка)
3. git reset --hard origin/{main_branch}
    Используется для сброса вашего локального репозитория к состоянию удаленной ветки, указанной в origin/{main_branch}.
    Сбрасывает не только указатель HEAD, но и рабочую директорию, а также индекс (staging area) к состоянию указанного коммита.
4. git clean -xdf
    Используется для удаления ВСЕХ неотслеживаемых файлов и директорий из вашего рабочего каталога.
5. Вывод статистики

!!! Предполагается, что сделанные бэкапы не используются !!! 
(Не производится переключение веток, добавление чего-то нового и тд. Бэкапы только лежат и обновляются скриптом)


Перед использованием установите необходимые библиотеки:
pip install PyGithub
! Этот скрипт требует Python версии 3.6 или выше !

Для запуска скрипта используйте команду:
Для выгрузки репозиториев организации "python save_repos.py your_token your_organization_name  organization "C:\\Users\\YourUsername\\Documents\\repositories""
Для выгрузки репозиториев пользователя "python save_repos.py your_token your_username user "C:\\Users\\YourUsername\\Documents\\repositories""
"""

from github import Github, BadCredentialsException, GithubException
import os
import subprocess
import argparse
import time
import sys

# Проверка версии Python
if sys.version_info < (3, 6):
    print("Этот скрипт требует Python версии 3.6 или выше.")
    sys.exit(1)

def get_directory_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # Skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def get_main_branch_name(repo_path):
    # Выполняем команду для получения списка всех веток
    result = subprocess.run(['git', '-C', repo_path, 'branch'], capture_output=True, text=True)
    branches = result.stdout.splitlines()
    
    # Проверяем, существуют ли ветки 'main' и 'master'
    has_main = '* main' in branches
    has_master = '* master' in branches

    """
    #DBG
    # Выводим содержимое переменной branches (отладка скрипта)
    print("DBG Branches:", branches)
    # Выводим значения переменных has_main и has_master
    print("has_main:", has_main)
    print("has_master:", has_master)
    """
    
    if has_main and has_master:
        print("Ошибка: Обе ветки 'main' и 'master' существуют одновременно.")
        return None
    elif has_main:
        return 'main'
    elif has_master:
        return 'master'
    else:
        return None

def main(token, name, entity_type, local_path):
    try:
        # Авторизация
        g = Github(token)
        # Получение пользователя для проверки аутентификацииh
        user = g.get_user()
        print(f"Аутентификация успешна. Пользователь: {user.login}\n")
    except BadCredentialsException:
        print("Ошибка аутентификации: Неверный токен доступа.")
        exit(1)
    except GithubException as e:
        print(f"Ошибка GitHub: {e}")
        exit(1)

    # Получение репозиториев пользователя или организации
    if entity_type == 'user':
        repos = g.get_user().get_repos(affiliation="owner")
    elif entity_type == 'organization':
        repos = g.get_organization(name).get_repos()
    else:
        print("Неверный тип сущности. Используйте 'user' или 'organization'.")
        exit(1)

    # Создание директории для сохранения репозиториев, если она не существует
    if not os.path.exists(local_path):
        os.makedirs(local_path)

    # Счетчики для подсчета количества репозиториев
    total_repos = 0
    updated_repos = 0
    cloned_repos = 0
    error_count = 0
    potential_errors_count = 0

    # Списки для хранения имен репозиториев
    cloned_repos_list = []
    updated_repos_list = []
    failed_repos_list = []
    
    # Костыль: считаем кол-во репозиториев в repos. Встроенный totalCount отображает неверено?
    for repo in repos:
        total_repos += 1
    
    # Клонирование каждого репозитория
    for index, repo in enumerate(repos):
        repo_name = repo.name
        repo_url = repo.clone_url
        repo_path = os.path.join(local_path, repo_name)
        
        # Проверка, существует ли уже локальная копия репозитория
        if not os.path.exists(repo_path):
            # Клонирование репозитория с повторной попыткой в случае ошибки
            print(f"{index + 1}/{total_repos}. Клонирование репозитория <{repo_name}>")
            success = False
            attempts = 0
            # есть странный баг, что репозиторий иногда не клонируется (клонирование с ошибкой), 
            # после завершения клонирования другого репозитория (жалуется на сеть), возможно задержка в несколько секунд поможет
            time.sleep(5)
            while not success and attempts < 5:
                result = subprocess.run(['git', 'clone', repo_url, repo_path])
                if result.returncode == 0:
                    success = True
                    cloned_repos += 1
                    cloned_repos_list.append(repo_name)
                    print(f"Репозиторий <{repo_name}> успешно склонирован.\n")
                else:
                    attempts += 1
                    potential_errors_count += 1
                    print(f"Ошибка при клонировании репозитория <{repo_name}>. Попытка {attempts}.")
                    time.sleep(10)  # Ожидание 10 секунд перед повторной попыткой
            if not success:
                print(f"Не удалось склонировать репозиторий <{repo_name}> после {attempts} попыток.\n")
                error_count += 1
                failed_repos_list.append(repo_name)
        # Если репозиторий уже существует, обновление существующего репозитория
        else:
            print(f"{index + 1}/{total_repos}. Репозиторий <{repo_name}> уже склонирован")
            error_flag = 0
            num_characters_fetch_output = 0
            # выполняем команду git fetch --all --prune
            result = subprocess.run(['git', '-C', repo_path, 'fetch', '--all', '--prune'], capture_output=True, text=True)
            if result.returncode == 0:
                #print(f"Успешно выполнена команда: git fetch --all --prune для репозитория <{repo_name}>")
                # Пытаемся определить по локальным веткам названием главной ветки (master или main)
                main_branch = get_main_branch_name(repo_path)
                if main_branch:
                    #print(f"Главная ветка: <{main_branch}> для репозитория <{repo_name}>")
                    # Получение вывода команды
                    stdout = result.stdout if result.stdout else ""
                    stderr = result.stderr if result.stderr else ""
                    output = stdout + stderr
                    # Подсчет количества символов в выводе
                    num_characters_fetch_output = len(output)
                    #print(f"DBG Количество символов в выводе fetch: {num_characters_fetch_output}")        
          
                    result = subprocess.run(['git', '-C', repo_path, 'reset', '--hard', f'origin/{main_branch}'], capture_output=True)
                    if result.returncode == 0:
                        #print(f"Успешно выполнена команда: git reset --hard origin/{main_branch}")
                        # Выполняем команду git clean -xdf (на всякий случай, удаляем файлы которые не относятся к репозиторию)
                        result = subprocess.run(['git', '-C', repo_path, 'clean', '-xdf'], capture_output=True)
                        if result.returncode == 0:
                            #print(f"Успешно выполнена команда: git clean -xdf для репозитория <{repo_name}>")
                            print('', end='')
                        else:
                            print(f"Ошибка при выполнении команды: {result.stderr}")
                            error_flag = 1
                    else:
                        print(f"Ошибка при выполнении команды: {result.stderr}")
                        error_flag = 1
                else:
                    print("Главная ветка не найдена или существует конфликт между ветками 'main' и 'master'.")
                    error_flag = 1
            else:
                print(f"Ошибка git fetch --all репозитория <{repo_name}>.")
                error_flag = 1          
            
            if error_flag == 0:
                if num_characters_fetch_output > 0:
                    msg = "изменения ЕСТЬ"
                    updated_repos += 1
                    updated_repos_list.append(repo_name)
                else:
                    msg = "изменений нет"            
                print(f"Репозиторий <{repo_name}> успешно обработан ({msg}).\n")
            else:
                print(f"Ошибка при обработке репозитория <{repo_name}>.\n")
                error_count += 1
                failed_repos_list.append(repo_name)

    print("====== INFO ======")
    print(f"Общее количество отслеживаемых репозиториев: {total_repos}")
    print(f"Количество клонированных репозиториев: {cloned_repos}")
    print(f"Количество обновленных репозиториев: {updated_repos}")
    print(f"Количество неисправленных ОШИБОК: {error_count}")
    #print(f"Количество потенциальных ОШИБОК: {potential_errors_count}") #DBG
    
    if cloned_repos > 0:
        print("====== список склонированных репозиториев ======")
        for repo in cloned_repos_list:
            print(f"- {repo}")
        print("\n")

    if updated_repos > 0:
        print("====== список обновленных репозиториев ======")
        for repo in updated_repos_list:
            print(f"- {repo}")
        print("\n")
    
    if error_count > 0:
        print("====== список репозиториев с которыми произошли ОШИБКИ ======")
        for repo in failed_repos_list:
            print(f"- {repo}")
        print("\n")
        
    # Вычисляем размер директории в байтах
    size_in_bytes = get_directory_size(local_path)
    # Переводим размер в гигабайты
    size_in_gigabytes = size_in_bytes / (1024 ** 3)
    print(f"Размер корневой директории: {size_in_gigabytes:.2f} ГБ")
    if error_count == 0:
        print("====== ОК! скрипт завершён (ошибок нет)! ======")
    else:
        print("====== ВНИМАНИЕ!!! скрипт завершён с ОШИБКАМИ !!! ======")
        


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Скачивание репозиториев пользователя или организации с GitHub.")
    parser.add_argument('token', help="Личный токен доступа GitHub")
    parser.add_argument('name', help="Имя пользователя или организации")
    parser.add_argument('entity_type', choices=['user', 'organization'], help="Тип сущности: 'user' или 'organization'")
    parser.add_argument('local_path', help="Путь для сохранения репозиториев")
    
    args = parser.parse_args()
    main(args.token, args.name, args.entity_type, args.local_path)