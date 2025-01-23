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
csv_path = "accounts.csv"  # Замените на путь к вашему CSV файлу
manual_login_and_save_cookies_from_csv(csv_path)