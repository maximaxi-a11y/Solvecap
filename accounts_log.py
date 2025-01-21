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

    extension_dir = os.path.join(os.getcwd(), f"proxys/proxy_auth_plugin_{proxy_ip}")
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




def curses_menu(stdscr):
    curses.curs_set(0)  # Скрыть курсор
    stdscr.clear()
    
    menu = ["1. Login and Save Cookies", "2. Manual Login and Save Cookies", "3. Load parameters from file", "4. Exit"]
    current_row = 0
    
    # Функция для отображения меню
    def print_menu():
        stdscr.clear()
        stdscr.addstr(0, 0, "Используйте стрелки вверх и вниз для навигации и Enter для выбора:", curses.A_BOLD)
        for idx, row in enumerate(menu):
            if idx == current_row:
                stdscr.addstr(idx + 2, 0, row, curses.color_pair(1))
            else:
                stdscr.addstr(idx + 2, 0, row)
        stdscr.refresh()
    
 
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
    
    while True:
        print_menu()
        key = stdscr.getch()
        
        if key == curses.KEY_UP and current_row > 0:
            current_row -= 1
        elif key == curses.KEY_DOWN and current_row < len(menu) - 1:
            current_row += 1
        elif key == ord("\n"):
            return current_row  


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


def main():
    def get_user_input(prompt):
        user_input = input(f"{prompt} (или 'q' для выхода): ").strip()
        if user_input.lower() == 'q':
            print("Выход из программы.")
            exit()
        return user_input
    
    while True:
        selected_option = curses.wrapper(curses_menu)
        
        if selected_option == 3:  
            print("Выход из программы.")
            break
        elif selected_option == 2:  
            filename = get_user_input("Введите имя файла с параметрами")
            load_parameters_from_file(filename)
            continue

        
        username = get_user_input("Введите имя пользователя")
        password = get_user_input("Введите пароль")
        question = get_user_input("Введите секретный вопрос (если требуется)")
        proxy = get_user_input("Введите прокси (в формате ip:port:username:password)")
        

        if selected_option == 0:
            print("\nВыполняется login_and_save_cookies...")
            success = login_and_save_cookies(username, password, question, proxy)
            if success:
                print("Куки успешно сохранены.")
            else:
                print("Не удалось сохранить куки.")
        
        elif selected_option == 1:
            print("\nВыполняется manual_login_and_save_cookies...")
            success = manual_login_and_save_cookies(username, password, question, proxy)
            if success:
                print("Куки успешно сохранены после ручного входа.")
            else:
                print("Не удалось сохранить куки после ручного входа.")
    

if __name__ == "__main__":
    main()
