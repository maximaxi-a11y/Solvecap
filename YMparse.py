import os
import re
import time
import csv
import pickle
import concurrent.futures
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
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument(f"--proxy-server=http://{proxy_ip}:{proxy_port}")

    proxy_auth_plugin_path = f'proxys/proxy_auth_plugin_{proxy_ip+proxy_port}.zip'
    print(proxy_auth_plugin_path)
    options.add_extension(proxy_auth_plugin_path)
    options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{account_id+70}.0.0.0 Safari/537.36")

    return options


def search_product_on_account(account_id, product_name, min_price, max_price, accounts):
    account_data = accounts[account_id - 1]
    username = account_data["username"]
    proxy = account_data["proxy"]

    options = configure_chrome_options(proxy, account_id)
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 10)

    cookies_path = f"cookies/cookies_{username}.pkl"
    print(username)
    account_min_price = None
    account_min_price_link = None

    try:
        driver.get("https://market.yandex.ru/")
        load_cookies(driver, cookies_path)
        driver.refresh()

        search_input = wait.until(EC.presence_of_element_located((By.ID, "header-search")))
        search_input.send_keys(product_name)

        search_button = driver.find_element(By.XPATH, "//button[@data-auto='search-button']")
        search_button.click()
        time.sleep(uniform(10,20))

        cheaper_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='подешевле']")))
        ActionChains(driver).move_to_element(cheaper_button).click(cheaper_button).perform()
        time.sleep(uniform(10,20))

        product_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-baobab-name="productSnippet"]')))

        for card in product_cards:
            try:
                price_container = card.find_element(By.XPATH, ".//*[@data-auto='snippet-price-current']")
                price_text_full = price_container.text
                price_match = re.search(r'\d+[\s\u00A0]*\d*', price_text_full)
                if price_match:
                    price_value = int(re.sub(r'[^\d]', '', price_match.group()))
                    product_link = card.find_element(By.XPATH, ".//a[contains(@href, '/product--')]").get_attribute("href")
                    if f'sku={product_name}' in product_link:
                        if account_min_price is None or price_value < account_min_price:
                            account_min_price = price_value
                            account_min_price_link = product_link
            except:
                print(f"Не удалось найти цену или ссылку для аккаунта {username}.")

        return (account_id, username, account_min_price, account_min_price_link)

    except Exception as e:
        print(f"Ошибка на аккаунте {username}: {e}")
        return (account_id, username, None, None)

    finally:
        driver.quit()


def search_on_multiple_accounts(sheet, max_price, account_count, csv_path):

    accounts = read_accounts_from_csv(csv_path)


    all_rows = sheet.get_all_values()


    drivers = {}
    for account_id in range(1, account_count + 1):
        account_data = accounts[account_id - 1]
        username = account_data["username"]
        proxy = account_data["proxy"]

        options = configure_chrome_options(proxy, account_id)
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)

        cookies_path = f"cookies/cookies_{username}.pkl"
        try:
            driver.get("https://market.yandex.ru/")
            load_cookies(driver, cookies_path)
            driver.refresh()
        except Exception as e:
            print(f"Ошибка инициализации браузера для аккаунта {username}: {e}")
            driver.quit()
            continue

        drivers[account_id] = {
            "driver": driver,
            "username": username,
        }

    
    def process_row(account_id, product_name):
        driver_info = drivers[account_id]
        driver = driver_info["driver"]
        username = driver_info["username"]

        wait = WebDriverWait(driver, 10)
        account_min_price = None
        account_min_price_link = None

        try:
            search_input = wait.until(EC.presence_of_element_located((By.ID, "header-search")))
            search_input.clear()
            search_input.send_keys(product_name)

            search_button = driver.find_element(By.XPATH, "//button[@data-auto='search-button']")
            search_button.click()
            time.sleep(uniform(10, 20))

            cheaper_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='подешевле']")))
            ActionChains(driver).move_to_element(cheaper_button).click(cheaper_button).perform()
            time.sleep(uniform(2, 4))
            evry = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, f"//*[text()='Искать везде']")))
            evry.click()
            time.sleep(uniform(10, 20))

            product_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-baobab-name="productSnippet"]')))

            for card in product_cards:
                try:
                    price_container = card.find_element(By.XPATH, ".//*[@data-auto='snippet-price-current']")
                    price_text_full = price_container.text
                    price_match = re.search(r'\d+[\s\u00A0]*\d*', price_text_full)
                    if price_match:
                        price_value = int(re.sub(r'[^\d]', '', price_match.group()))
                        card_text = card.text
                        product_link = card.find_element(By.XPATH, ".//a[contains(@href, '/product--')]").get_attribute("href")
                        if f'sku={product_name}' in product_link and 'рубежа' in card_text.lower():
                            if account_min_price is None or price_value < account_min_price:
                                account_min_price = price_value
                                account_min_price_link = product_link
                except:
                    print(f"Не удалось найти цену или ссылку для аккаунта {username}.")
        except Exception as e:
            print(f"Ошибка на аккаунте {username}: {e}")

        return account_id, username, account_min_price, account_min_price_link


    for row_index, row in enumerate(all_rows[1:], start=2):
        product_name = row[1] 

        
        if not product_name.strip():
            print(f"Row {row_index}: Skipping empty product_name.")
            continue

        print(f"Processing product: {product_name} (Row {row_index})")
        results = []
        failed_accounts = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=account_count) as executor:
            futures = [executor.submit(process_row, account_id, product_name) for account_id in drivers.keys()]

            for future in concurrent.futures.as_completed(futures):
                try:
                    account_id, username, price, link = future.result()
                    if price is not None:
                        results.append((account_id, username, price, link))
                    else:
                        failed_accounts.append(account_id)
                except Exception as e:
                    print(f"Ошибка в потоке: {e}")
                    failed_accounts.append(account_id)

       
        price_to_accounts = {}
        for _, username, price, link in results:
            if price is not None:
                if price not in price_to_accounts:
                    price_to_accounts[price] = []
                price_to_accounts[price].append((username, link))

       
        if price_to_accounts:
            overall_min_price = min(price_to_accounts.keys())
            accounts_with_min_price = price_to_accounts[overall_min_price]

            account_names = ", ".join(username for username, _ in accounts_with_min_price)
            links = ", ".join(link for _, link in accounts_with_min_price)

          
            sheet.update_cell(row_index, 3, overall_min_price) 
            sheet.update_cell(row_index, 4, links) 
            sheet.update_cell(row_index, 5, account_names) 

            print(f"Row {row_index}: Minimum price: {overall_min_price} ₽, Accounts: {account_names}, Links: {links}")
        else:
            print(f"Row {row_index}: No price found for {product_name}.")
            sheet.update_cell(row_index, 3, "Not found") 
            sheet.update_cell(row_index, 4, "Not found")  
            sheet.update_cell(row_index, 5, "Not found")  

        if failed_accounts:
            print(f"Row {row_index}: Failed accounts (possibly encountered CAPTCHA): {failed_accounts}")

    
    for driver_info in drivers.values():
        driver_info["driver"].quit()


sheet = connect_to_google_sheets("Sellerbot")

# Пример вызова функции
search_on_multiple_accounts(sheet,1000000, 4,csv_path='accounts.csv')