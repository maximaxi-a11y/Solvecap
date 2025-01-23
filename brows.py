import os
import pickle
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from .accounts_log import setup_driver

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