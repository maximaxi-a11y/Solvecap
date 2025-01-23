import os
import re
import time
import csv
import pickle
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from random import uniform
from cap_solve import solve_cap
import threading
import traceback


chromedriver_path = 'chromedriver-win32/chromedriver.exe'


def read_accounts_from_csv(file_path):
    accounts = []
    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            accounts.append({
                "username": row["username"],
                "password": row["password"],
                "question": row["question"],
                "proxy": row["proxy"]
            })
    return accounts


def connect_to_google_sheets(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive.file",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet


def load_cookies(driver, cookies_path):
    if os.path.exists(cookies_path):
        with open(cookies_path, "rb") as cookies_file:
            cookies = pickle.load(cookies_file)
            for cookie in cookies:
                driver.add_cookie(cookie)
    else:
        print(f"Cookie файл {cookies_path} не найден.")


def configure_chrome_options(proxy, account_id):
    proxy_ip, proxy_port, proxy_user, proxy_pass = proxy.split(":")
    print(proxy_ip)
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--headless=new")
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument(f"--proxy-server=http://{proxy_ip}:{proxy_port}")

    proxy_auth_plugin_path = f'proxys/proxy_auth_plugin_{proxy_ip+proxy_port}.zip'
    print(proxy_auth_plugin_path)
    options.add_extension(proxy_auth_plugin_path)
    options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{account_id+70}.0.0.0 Safari/537.36")

    return options



def update_google_sheet(sheet, local_csv_dir, account_count):
    """
    Агрегация данных из локальных CSV-файлов и запись минимальных цен в Google Таблицу.
    """
    final_results = {} 

  
    for account_id in range(1, account_count + 1):
        local_csv_file = os.path.join(local_csv_dir, f"account_{account_id}.csv")
        if os.path.exists(local_csv_file):
            with open(local_csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    row_index = int(row[0])
                    product_name = row[1]
                    price = row[2]
                    link = row[3]
                    username = row[4]

            
                    if product_name not in final_results:
                        final_results[product_name] = []
                    final_results[product_name].append((row_index, price, link, username))

    for product_name, results in final_results.items():
        if not results:
            continue
        min_price_entry = min(
            results, key=lambda x: int(x[1]) if x[1] and x[1].isdigit() else float("inf")
        )
        row_index, price, link, username = min_price_entry

        sheet.update_cell(row_index, 3, price)  
        sheet.update_cell(row_index, 4, link)   
        sheet.update_cell(row_index, 5, username) 

    print("Все данные успешно обновлены в Google Таблице.")




def search_on_multiple_accounts(sheet, max_price, account_count, csv_path, local_csv_dir):
    accounts = read_accounts_from_csv(csv_path)
    all_rows = sheet.get_all_values()

    if not os.path.exists(local_csv_dir):
        os.makedirs(local_csv_dir)
    else:
        for file_name in os.listdir(local_csv_dir):
            if file_name.endswith(".csv"):
                file_path = os.path.join(local_csv_dir, file_name)
                os.remove(file_path)
        print(f"Очистка локальных таблиц ({local_csv_dir}) завершена.")

    failed_accounts = []

    def save_cookies(driver, path):
        with open(path, "wb") as file:
            pickle.dump(driver.get_cookies(), file)

    def process_account(account_id):
        account_data = accounts[account_id - 1]
        username = account_data["username"]
        proxy = account_data["proxy"]

        local_csv_file = os.path.join(local_csv_dir, f"{username}.csv")

        options = configure_chrome_options(proxy, account_id)
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)

        cookies_path = f"cookies/cookies_{username}.pkl"
        evry_element_skipped = False

        try:
            driver.get("https://market.yandex.ru/")
            load_cookies(driver, cookies_path)
            driver.refresh()

            if driver.find_elements(By.XPATH, "//*[contains(text(), 'Войти')]"):
                print(f"Аккаунт {username} не авторизован. Закрываем и добавляем в список неисправных.")
                failed_accounts.append(username)
                driver.quit()
                return

        except Exception as e:
            print(f"Ошибка инициализации браузера для аккаунта {username}: {e}")
            driver.quit()
            return

        def handle_captcha():
            try:
                captcha_text_present = driver.find_elements(By.XPATH, "//*[contains(text(), 'а не робот')]")
                captcha_checkbox = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'js-button'))
                )
                if captcha_text_present and captcha_checkbox:
                    print(f"CAPTCHA обнаружена на аккаунте {username}. Пытаемся решить...")
                    solve_cap(driver)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "header-search"))
                    )
                    print(f"CAPTCHA успешно решена для аккаунта {username}. Обновляем куки.")
                    save_cookies(driver, cookies_path)
                    return True
            except Exception as e:
                print(f"Ошибка при решении CAPTCHA для аккаунта {username}: {e}")
                return False

        for row_index, row in enumerate(all_rows[1:], start=2):
            product_name = row[1]
            if not product_name.strip():
                continue

            retry_count = 0
            while retry_count < 5:
                try:
                    wait = WebDriverWait(driver, 10)
                    search_input = wait.until(EC.presence_of_element_located((By.ID, "header-search")))
                    search_input.clear()
                    search_input.send_keys(product_name)

                    search_button = driver.find_element(By.XPATH, "//button[@data-auto='search-button']")
                    search_button.click()
                    time.sleep(uniform(10, 20))

                    cheaper_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='подешевле']")))
                    ActionChains(driver).move_to_element(cheaper_button).click(cheaper_button).perform()
                    time.sleep(uniform(2, 4))

                    if not evry_element_skipped:
                        try:
                            evry = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, f"//*[text()='Искать везде']"))
                            )
                            evry.click()
                            time.sleep(uniform(10, 20))
                        except:
                            print(f"Элемент 'Искать везде' не найден на аккаунте {username}. Пропускаем его в будущем.")
                            evry_element_skipped = True

                    product_cards = wait.until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-baobab-name="productSnippet"]'))
                    )

                    min_price = None
                    min_price_link = None

                    for card in product_cards:
                        try:
                            price_container = card.find_element(By.XPATH, ".//*[@data-auto='snippet-price-current']")
                            price_text_full = price_container.text
                            price_match = re.search(r'\d+[\s\u00A0]*\d*', price_text_full)
                            if price_match:
                                price_value = int(re.sub(r'[^\d]', '', price_match.group()))
                                product_link = card.find_element(By.XPATH, ".//a[contains(@href, '/product--')]").get_attribute("href")
                                if min_price is None or price_value < min_price:
                                    min_price = price_value
                                    min_price_link = product_link
                        except:
                            continue

                    with open(local_csv_file, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([row_index, product_name, min_price, min_price_link, username])

                    break

                except Exception:
                    error_message = traceback.format_exc()
                    print(f"Ошибка на аккаунте {username}, строка {row_index}: {error_message}")
                    captcha_text_present = driver.find_elements(By.XPATH, "//*[contains(text(), 'а не робот')]")
                    captcha_checkbox = driver.find_elements(By.ID, 'js-button')
                    if captcha_text_present and captcha_checkbox:
                        if not handle_captcha():
                            print(f"Аккаунт {username} заблокирован из-за невозможности пройти CAPTCHA.")
                            driver.quit()
                            return
                        else:
                            print(f"CAPTCHA решена, но ошибка сохраняется. Перезапускаем текущий шаг для аккаунта {username}.")
                            continue
                    else:
                        retry_count += 1
                        if retry_count >= 5:
                            print(f"Слишком много ошибок на аккаунте {username}, строка {row_index}. Пропускаем строку.")
                            break

        driver.quit()

    threads = []
    for account_id in range(1, account_count + 1):
        thread = threading.Thread(target=process_account, args=(account_id,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("Обработка всех аккаунтов завершена.")



    if failed_accounts:
        print("Список неисправных аккаунтов:")
        for username in failed_accounts:
            print(f"- {username}")


    update_google_sheet(sheet, local_csv_dir, account_count)

sheet = connect_to_google_sheets("Parser_test")


search_on_multiple_accounts(sheet,1000000, 3,csv_path='accounts.csv',local_csv_dir='csvs')