import os
import zipfile
import pickle
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from random import uniform
import shutil
import curses
import csv

service = Service('chromedriver-win32\chromedriver.exe')

error_accounts = []



def create_proxy_auth_extension(proxy_ip, proxy_port, proxy_user, proxy_pass):
    plugin_content = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "http",
                host: "{proxy_ip}",
                port: parseInt("{proxy_port}")
            }},
            bypassList: ["localhost"]
        }}
    }};
    
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy_user}",
                password: "{proxy_pass}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ["blocking"]
    );
    """

    extension_dir = os.path.join(os.getcwd(), f"proxys/proxy_auth_plugin_{proxy_ip+proxy_ip}")
    os.makedirs(extension_dir, exist_ok=True)

    manifest_content = """{
        "version": "1.0",
        "manifest_version": 2,
        "name": "Chrome Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }"""

    manifest_path = os.path.join(extension_dir, "manifest.json")
    with open(manifest_path, "w") as manifest_file:
        manifest_file.write(manifest_content)
    
    background_path = os.path.join(extension_dir, "background.js")
    with open(background_path, "w") as background_file:
        background_file.write(plugin_content)

    zip_path = f"{extension_dir}.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        zip_file.write(manifest_path, "manifest.json")
        zip_file.write(background_path, "background.js")


    shutil.rmtree(extension_dir)

    return zip_path

def setup_driver(proxy):

    proxy_parts = proxy.split(':')
    if len(proxy_parts) == 4:
        proxy_ip, proxy_port, proxy_user, proxy_pass = proxy_parts
    else:
        raise ValueError("Proxy string must be in the format 'ip:port:username:password'")


    proxy_extension = create_proxy_auth_extension(proxy_ip, proxy_port, proxy_user, proxy_pass)

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--ignore-certificate-errors-spki-list')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_extension(proxy_extension)
    
    return webdriver.Chrome(service=service, options=chrome_options)

def login_and_save_cookies(username, password, question, proxy):
    driver = setup_driver(proxy)
    wait = WebDriverWait(driver, 10)
    success = False
    error_accounts = []

    try:
        driver.get("https://market.yandex.ru/")
        time.sleep(uniform(2, 5))
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-zone-name='headerLoginButton']//a")))
        login_button.click()
        time.sleep(uniform(2, 5))
        add_account_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[.//span[contains(text(), 'Почта')]]")))
        time.sleep(uniform(2, 5))
        add_account_button.click()
        time.sleep(uniform(2, 5))
        username_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@data-t='field:input-login']")))
        time.sleep(uniform(2, 5))
        username_input.send_keys(username)

        pass_but = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@data-t='button:action:passp:sign-in']")))
        time.sleep(uniform(2, 5))
        pass_but.click()

        password_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='passp-field-passwd' and @name='passwd' and @type='password']")))
        time.sleep(uniform(2, 5))
        password_input.send_keys(password)
        time.sleep(uniform(2, 5))
        password_input.send_keys(Keys.ENTER)

        try:
            question_field = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='passp-field-question' and @name='question' and @type='text']")))
            time.sleep(uniform(2, 5))
            question_field.send_keys(question)
            time.sleep(uniform(2, 5))
            question_field.send_keys(Keys.ENTER)
        except:
            pass  

        
        if "Восстановить" in driver.page_source:
            error_accounts.append(username)
        else:
            time.sleep(uniform(2, 5))
            
            
            cookies_path = f"cookies/cookies_{username}.pkl"
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, "wb") as cookies_file:
                pickle.dump(driver.get_cookies(), cookies_file)
            success = True

            accounts_file = "accounts.csv"
            if os.path.exists(accounts_file):
                accounts_df = pd.read_csv(accounts_file)
            else:
                accounts_df = pd.DataFrame(columns=["username", "password", "question", "proxy"])

   
            account_entry = pd.DataFrame([{
                "username": username,
                "password": password,
                "question": question,
                "proxy": proxy
            }])
            accounts_df = pd.concat([accounts_df, account_entry], ignore_index=True)

            accounts_df.to_csv(accounts_file, index=False)
            print(f"Account details saved successfully in {accounts_file}")

    except Exception as e:
        error_accounts.append(username)
        print(f"Error logging in for {username}: {e}")
    finally:
        driver.quit()

    return success

if error_accounts:
    print("\nManual login required for the following accounts:")
    for account_name in error_accounts:
        print(f"Account {account_name} requires manual login.")



def manual_login_and_save_cookies(username, password, question, proxy):
    driver = setup_driver(proxy)

    cookies_saved = False

    try:
        driver.get("https://market.yandex.ru/")
        print(f"Please log in manually for account: {username}")
        print("After completing the login, press Enter to save cookies.")
        print("If you want to cancel the session, press 'q' and then Enter.")

        user_input = input("Press Enter to save cookies or 'q' to cancel: ").strip().lower()
        
        if user_input == 'q':
            print("Login session cancelled by the user.")
            return False 
        
       
        cookies_path = f"cookies/cookies_{username}.pkl"
        os.makedirs(os.path.dirname(cookies_path), exist_ok=True)  

        with open(cookies_path, "wb") as cookies_file:
            pickle.dump(driver.get_cookies(), cookies_file)
        cookies_saved = True
        print(f"Cookies saved successfully for {username} at {cookies_path}")

        accounts_file = "accounts.csv"
        if os.path.exists(accounts_file):
            accounts_df = pd.read_csv(accounts_file)
        else:
            accounts_df = pd.DataFrame(columns=["username", "password", "question", "proxy"])

        account_entry = pd.DataFrame([{
            "username": username,
            "password": password,
            "question": question,
            "proxy": proxy
        }])
        
        accounts_df = pd.concat([accounts_df, account_entry], ignore_index=True)

        accounts_df.to_csv(accounts_file, index=False)
        print(f"Account details saved successfully in {accounts_file}")
    
    except Exception as e:
        print(f"Error during manual login for {username}: {e}")
    finally:
        driver.quit()

    return cookies_saved


def load_parameters_from_file(filename):
    try:
        with open(filename, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if len(row) != 4:
                    print(f"Ошибка: строка {row} имеет неправильное количество параметров. Пропуск строки.")
                    continue
                username, password, question, proxy = row
                print(f"Выполняется login_and_save_cookies для пользователя {username}...")
                success = login_and_save_cookies(username, password, question, proxy)
                if success:
                    print(f"Куки для пользователя {username} успешно сохранены.")
                else:
                    print(f"Не удалось сохранить куки для пользователя {username}.")
    except FileNotFoundError:
        print(f"Файл {filename} не найден.")
    except Exception as e:
        print(f"Ошибка при чтении файла {filename}: {e}")



def manual_login_and_save_cookies_from_csv(csv_path):
    """
    Функция читает данные из CSV файла, выполняет ручной вход и сохраняет cookies для каждой учетной записи.
    
    :param csv_path: Путь к CSV файлу с данными учетных записей (username, password, question, proxy).
    """
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return

    # Считываем CSV файл
    try:
        accounts_df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Ошибка чтения CSV файла: {e}")
        return

    # Проверяем наличие необходимых столбцов
    required_columns = {"username", "password", "question", "proxy"}
    if not required_columns.issubset(accounts_df.columns):
        print(f"CSV файл должен содержать столбцы: {', '.join(required_columns)}")
        return

    # Проходим по каждой строке CSV файла
    for index, row in accounts_df.iterrows():
        username = row["username"]
        password = row["password"]
        question = row["question"]
        proxy = row["proxy"]

        driver = setup_driver(proxy)
        cookies_saved = False

        try:
            driver.get("https://market.yandex.ru/")
            print(f"Пожалуйста, выполните вход вручную для учетной записи: {username}")
            print("После завершения входа нажмите Enter для сохранения cookies.")
            print("Если хотите отменить сессию, нажмите 'q' и затем Enter.")

            user_input = input("Нажмите Enter для сохранения cookies или 'q' для отмены: ").strip().lower()

            if user_input == 'q':
                print(f"Сессия входа для {username} отменена пользователем.")
                continue

            # Сохраняем cookies в файл
            cookies_path = f"cookies/cookies_{username}.pkl"
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)

            with open(cookies_path, "wb") as cookies_file:
                pickle.dump(driver.get_cookies(), cookies_file)
            cookies_saved = True
            print(f"Cookies успешно сохранены для {username} в {cookies_path}")

        except Exception as e:
            print(f"Ошибка во время ручного входа для {username}: {e}")

        finally:
            driver.quit()

        if cookies_saved:
            print(f"Процесс для {username} завершен успешно.")
        else:
            print(f"Процесс для {username} завершен с ошибкой.")

# Пример использования
def process_proxies(csv_file_path):
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            
            # Проверяем, что необходимые столбцы присутствуют в CSV
            required_columns = ['proxy', 'username']
            for column in required_columns:
                if column not in reader.fieldnames:
                    raise ValueError(f"CSV file does not contain the required column: {column}")
            
            for row in reader:
                proxy = row['proxy']
                username = row['username']
                
                proxy_parts = proxy.split(':')
                if len(proxy_parts) != 4:
                    print(f"Skipping invalid proxy format: {proxy}")
                    continue
                
                proxy_ip, proxy_port, proxy_user, proxy_pass = proxy_parts
                
                # Передаем части прокси и username в функцию
                proxy_extension = create_proxy_auth_extension(proxy_ip, proxy_port, proxy_user, proxy_pass)
                print(f"Created proxy extension: {proxy_extension}")
    
    except FileNotFoundError:
        print(f"CSV file not found: {csv_file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")




def load_browser_with_cookies(username, csv_path):
    """
    Открывает браузер с cookies и прокси на основе имени пользователя.

    :param username: Имя пользователя, для которого нужно загрузить cookies.
    :param csv_path: Путь к CSV файлу с данными учетных записей.
    """
    cookies_path = f"cookies/cookies_{username}.pkl"
    if not os.path.exists(cookies_path):
        print(f"Cookies для пользователя {username} не найдены в {cookies_path}")
        return

    # Чтение данных из CSV
    try:
        accounts_df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Ошибка чтения CSV файла: {e}")
        return

    # Поиск строки с указанным пользователем
    user_data = accounts_df[accounts_df["username"] == username]
    if user_data.empty:
        print(f"Данные для пользователя {username} не найдены в CSV файле.")
        return

    proxy = user_data.iloc[0]["proxy"]

    driver = setup_driver(proxy)

    try:
        driver.get("https://market.yandex.ru/")

        # Загрузка cookies в браузер
        with open(cookies_path, "rb") as cookies_file:
            cookies = pickle.load(cookies_file)

        for cookie in cookies:
            driver.add_cookie(cookie)

        print(f"Cookies для {username} успешно загружены.")

        # Перезагружаем страницу, чтобы применить cookies
        driver.refresh()

    except Exception as e:
        print(f"Ошибка при загрузке браузера с cookies для {username}: {e}")
    finally:
        input("Нажмите Enter, чтобы закрыть браузер.")
        driver.quit()

# Пример использования
csv_path = "accounts.csv"  # Замените на путь к вашему CSV файлу
username = input()  # Замените на имя пользователя
load_browser_with_cookies(username, csv_path)

