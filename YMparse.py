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



# def update_google_sheet(sheet, local_csv_dir, account_count):
#     aggregated_data = collections.defaultdict(lambda: {'sku': None, 'prices': {}})
    
#     # Читаем все локальные CSV-файлы и агрегируем данные
#     for file_name in os.listdir(local_csv_dir):
#         if file_name.endswith(".csv"):
#             file_path = os.path.join(local_csv_dir, file_name)
#             username = os.path.splitext(file_name)[0]
            
#             with open(file_path, "r", newline="", encoding="utf-8") as f:
#                 reader = csv.reader(f)
#                 for row in reader:
#                     if len(row) < 4:
#                         continue
                    
#                     row_index, product_name, price, product_link = row[:4]
                    
#                     if not price or not price.isdigit():
#                         continue
                    
#                     price = int(price)
#                     sku = f"SKU_{row_index}"  # SKU из строки таблицы
                    
#                     if aggregated_data[sku]['sku'] is None:
#                         aggregated_data[sku]['sku'] = sku
                    
#                     if price not in aggregated_data[sku]['prices']:
#                         aggregated_data[sku]['prices'][price] = {'link': product_link, 'accounts': set()}
                    
#                     aggregated_data[sku]['prices'][price]['accounts'].add(username)
    
#     # Подготавливаем данные для записи в Google Sheets
#     sorted_data = []
#     for sku, data in aggregated_data.items():
#         for price, info in data['prices'].items():
#             sorted_data.append([
#                 sku, price, info['link'], ", ".join(info['accounts'])
#             ])
    
#     # Загружаем данные в Google Sheets
#     if sorted_data:
#         sheet_range = "Sheet1!B:E"  # Укажите нужный диапазон
#         sheet.values().clear(spreadsheetId=SHEET_ID, range=sheet_range).execute()
#         sheet.values().update(
#             spreadsheetId=SHEET_ID,
#             range=sheet_range,
#             valueInputOption="RAW",
#             body={"values": sorted_data}
#         ).execute()
    
#     print("Данные успешно обновлены в Google Sheets.")


def update_google_sheet(csv_file, sheet):
    worksheet = sheet  # Первый лист
    
    # 3. Загружаем данные из Google Таблицы
    sheet_data = worksheet.get_all_values()
    
    # 4. Загружаем CSV и группируем данные по SKU
    sku_records = {}
    with open(csv_file, newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            table_row, sku, price, link, username = row
            if not price.strip():  # Пропускаем пустые цены
                continue
            price = float(price)
            if sku not in sku_records:
                sku_records[sku] = []
            sku_records[sku].append((price, link, username))
    
    # 5. Обновляем таблицу
    for i, row in enumerate(sheet_data, start=1):
        if len(row) > 1 and row[1] in sku_records and sku_records[row[1]]:  # SKU во втором столбце и есть записи
            sku = row[1]
            # Находим запись с минимальной ценой
            min_price_record = min(sku_records[sku], key=lambda x: x[0])
            price, link, username = min_price_record
            worksheet.update(f"C{i}:E{i}", [[price, link, username]])  # Обновляем три столбца сразу
    
    print("Обновление Google Таблицы завершено.")





def search_on_multiple_accounts(sheet, max_price, account_count, csv_path, local_csv_dir, output_csv='parsed_results.csv'):
    accounts = read_accounts_from_csv(csv_path)
    all_rows = sheet.get_all_values()

    if not os.path.exists(local_csv_dir):
        os.makedirs(local_csv_dir)
    
    output_csv_path = os.path.join(local_csv_dir, output_csv)
    if os.path.exists(output_csv_path):
        os.remove(output_csv_path)
    
    failed_accounts = []

    def save_cookies(driver, path):
        with open(path, "wb") as file:
            pickle.dump(driver.get_cookies(), file)

    def process_account(account_id):
        account_data = accounts[account_id - 1]
        username = account_data["username"]
        proxy = account_data["proxy"]

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
                    solve_cap(driver, username)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "header-search"))
                    )
                    print(f"CAPTCHA успешно решена для аккаунта {username}. Обновляем куки.")
                    save_cookies(driver, cookies_path)
                    return True
            except Exception as e:
                print(f"Ошибка при решении CAPTCHA для аккаунта {username}: {e}")
                return False

        with open(output_csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row_index, row in enumerate(all_rows[1:], start=2):
                product_name = row[1]

                if not product_name.strip():
                    continue

                retry_count = 0
                while retry_count < 3:
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
                                    EC.element_to_be_clickable((By.XPATH, "//*[text()='Искать везде']"))
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
                                    print(product_link,product_name)
                                    if f'{product_name}' in product_link:
                                        if min_price is None or price_value < min_price:
                                            min_price = price_value
                                            min_price_link = product_link
                                    else:
                                        print(f"⚠️ Пропущен товар: SKU {product_name} отсутствует в ссылке {product_link}")

                            except:
                                continue
                        writer.writerow([row_index, product_name, min_price, min_price_link, username])
                        break

                    except Exception:
                        print(f"Ошибка на аккаунте {username}, строка {row_index}: {traceback.format_exc()}")
                        if driver.find_elements(By.XPATH, "//*[contains(text(), 'а не робот')]"):
                            if not handle_captcha():
                                screenshot_path = f"after{username}.png"
                                driver.save_screenshot(screenshot_path)
                                print(f"Аккаунт {username} заблокирован из-за невозможности пройти CAPTCHA.")
                                driver.quit()
                                return
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

    update_google_sheet('csvs/parsed_results.csv',sheet)


sheet = connect_to_google_sheets("Parser_test")

search_on_multiple_accounts(sheet,1000000, 1,csv_path='accounts.csv',local_csv_dir='csvs')
