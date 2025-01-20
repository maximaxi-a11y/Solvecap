from telegram import Update, Document
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import schedule
import time
from threading import Thread
from datetime import datetime
from YMparse import connect_to_google_sheets, search_on_multiple_accounts
from accounts_log import create_proxy_auth_extension
import os
import csv



STATIC_CSV_PATH = "accounts.csv"
COOKIES_DIR = "cookies"
PROXY_EXT_DIR = "."

user_states = {}
scheduler_thread = None
current_interval_minutes = None
stop_scheduler = False
PROXY_EXT_DIR = "."
pending_users = {}
stop_cookies = False

async def create_users_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CSV uploads for batch user creation."""
    document = update.message.document
    if document is None:
        await update.message.reply_text("Please attach a valid CSV file when using the /create_users_batch command.")
        return

    if not document.file_name.endswith(".csv"):
        await update.message.reply_text("The uploaded file must be a .csv file.")
        return

    csv_path = os.path.join(PROXY_EXT_DIR, document.file_name)
    os.makedirs(PROXY_EXT_DIR, exist_ok=True)

 
    file = await document.get_file()
    await file.download_to_drive(csv_path)


    existing_users = set()
    if os.path.exists(STATIC_CSV_PATH):
        with open(STATIC_CSV_PATH, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if "username" in row:
                    existing_users.add(row["username"].strip().lower())

    try:
        valid_users = []
        with open(csv_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if "username" in row and "password" in row and "question" in row and "proxy" in row:
                    username = row["username"].strip().lower()
                    if username in existing_users:
                        await update.message.reply_text(f"User '{row['username']}' already exists. Skipping.")
                        continue

                    proxy_parts = row["proxy"].split(":")
                    if len(proxy_parts) != 4:
                        await update.message.reply_text(
                            f"Invalid proxy format for user '{row['username']}': {row['proxy']}. Skipping."
                        )
                        continue

                    proxy_ip, proxy_port, proxy_user, proxy_pass = proxy_parts
                    proxy_extension_path = create_proxy_auth_extension(proxy_ip, proxy_port, proxy_user, proxy_pass)
                    if proxy_extension_path:
                        await update.message.reply_text(
                            f"Proxy extension created for user '{row['username']}' at: {proxy_extension_path}"
                        )
                    else:
                        await update.message.reply_text(
                            f"Failed to create proxy extension for user '{row['username']}'."
                        )

                    valid_users.append(row)
                else:
                    await update.message.reply_text(
                        f"Invalid format in row: {row}. Ensure all columns are present (username, password, question, proxy)."
                    )

        with open(STATIC_CSV_PATH, "a", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["username", "password", "question", "proxy"])
            if os.stat(STATIC_CSV_PATH).st_size == 0:  
                writer.writeheader()
            for user in valid_users:
                if user["username"].strip().lower() not in existing_users:
                    writer.writerow(user)
                    existing_users.add(user["username"].strip().lower())

        os.remove(csv_path)
        await update.message.reply_text(
            f"Batch user creation completed. Total valid users added: {len(valid_users)}."
        )
    except Exception as e:
        await update.message.reply_text(f"Error processing CSV file: {e}")
        if os.path.exists(csv_path): 
            os.remove(csv_path)

async def handle_cookies_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploading cookies for each user."""
    global stop_cookies
    if stop_cookies:
        await update.message.reply_text("Cookie uploads stopped. Please restart the bot for new uploads.")
        return

    document = update.message.document
    if not document.file_name.startswith("cookies_") or not document.file_name.endswith(".pkl"):
        await update.message.reply_text("Invalid file format. Upload cookies as cookies_<username>.pkl.")
        return

    
    username = document.file_name.replace("cookies_", "").replace(".pkl", "").strip().lower()

    accounts_file_path = STATIC_CSV_PATH  
    if not os.path.exists(accounts_file_path):
        await update.message.reply_text("Accounts file not found. Ensure the bot is properly configured.")
        return

    user_exists = False
    try:
        with open(accounts_file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                
                if row.get("username", "").strip().lower() == username:
                    user_exists = True
                    break
    except Exception as e:
        await update.message.reply_text(f"Error reading accounts file: {e}")
        return

    if not user_exists:
        await update.message.reply_text(f"Unknown username '{username}' for this cookie file. Ensure it matches.")
        return

 
    cookie_path = os.path.join(COOKIES_DIR, document.file_name)
    os.makedirs(COOKIES_DIR, exist_ok=True)

    file = await document.get_file()
    await file.download_to_drive(cookie_path)
    await update.message.reply_text(f"Cookie file for {username} successfully uploaded.")

async def stop_cookies_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to stop cookie uploads."""
    global stop_cookies
    stop_cookies = True
    await update.message.reply_text("Cookie upload process stopped. Ready for new commands.")





async def show_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if os.path.exists(STATIC_CSV_PATH):
            await update.message.reply_document(document=open(STATIC_CSV_PATH, "rb"))
            print(f"Файл {STATIC_CSV_PATH} отправлен пользователю.")
        else:
            await update.message.reply_text("Файл accounts.csv не найден.")
            print("Файл accounts.csv не найден.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при отправке файла: {e}")
        print(f"Ошибка при отправке файла: {e}")


def task_runner(sheet_name, min_price, max_price, account_count, csv = STATIC_CSV_PATH):
    print(f"[{datetime.now()}] Запуск search_on_multiple_accounts...")
    try:
        sheet = connect_to_google_sheets(sheet_name)
        search_on_multiple_accounts(sheet, min_price, max_price, account_count,csv_path=csv)
        print(f"[{datetime.now()}] Функция выполнена.")
    except Exception as e:
        print(f"[{datetime.now()}] Ошибка выполнения: {e}")

def start_scheduler(interval_minutes, sheet_name, min_price, max_price, account_count):
    global stop_scheduler
    schedule.every(interval_minutes).minutes.do(task_runner, sheet_name, min_price, max_price, account_count)
    print(f"Планировщик запущен. Интервал: {interval_minutes} минут.")
    while not stop_scheduler:
        schedule.run_pending()
        time.sleep(1)



async def run_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sheet_name, min_price, max_price, account_count = context.args
        min_price = int(min_price)
        max_price = int(max_price)
        account_count = int(account_count)

        task_runner(sheet_name, min_price, max_price, account_count)
        await update.message.reply_text("Функция выполнена вручную.")
    except ValueError:
        await update.message.reply_text("Неверные параметры. Пример: /run SheetName 100 5000 5")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global scheduler_thread, current_interval_minutes, stop_scheduler

    try:
        interval_minutes = int(context.args[0])
        sheet_name, min_price, max_price, account_count = context.args[1:]
        min_price = int(min_price)
        max_price = int(max_price)
        account_count = int(account_count)

        if interval_minutes <= 0:
            raise ValueError("Интервал должен быть больше нуля.")

        if scheduler_thread and scheduler_thread.is_alive():
            stop_scheduler = True
            scheduler_thread.join()
            stop_scheduler = False

        await update.message.reply_text("Немедленный запуск функции...")
        task_runner(sheet_name, min_price, max_price, account_count)

        current_interval_minutes = interval_minutes
        scheduler_thread = Thread(target=start_scheduler, args=(interval_minutes, sheet_name, min_price, max_price, account_count))
        scheduler_thread.daemon = True
        scheduler_thread.start()

        await update.message.reply_text(
            f"Интервал обновлён. Функция будет запускаться каждые {interval_minutes} минут.\n"
            f"Параметры: Sheet: {sheet_name}, MinPrice: {min_price}, MaxPrice: {max_price}, Accounts: {account_count}"
        )
    except ValueError:
        await update.message.reply_text(
            "Неверные параметры. Пример: /setinterval 10 SheetName 100 5000 5"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def cancel_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global scheduler_thread, stop_scheduler

    if scheduler_thread and scheduler_thread.is_alive():
        stop_scheduler = True
        scheduler_thread.join()
        stop_scheduler = False
        await update.message.reply_text("Расписание отменено.")
    else:
        await update.message.reply_text("Расписание уже остановлено.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для управления search_on_multiple_accounts.\n"
        "Доступные команды:\n"
        "/run <sheet_name> <min_price> <max_price> <account_count> - Запустить функцию вручную\n"
        "/setinterval <минуты> <sheet_name> <min_price> <max_price> <account_count> - Настроить интервал\n"
        "/cancel - Отменить расписание\n"
        "/showcsv - Показать текущий файл accounts.csv\n"
        "/delete_user <username> - Удалить пользователя по имени\n"
        "/create_users_batch - Upload a CSV file to batch add users.\n"
        "/stop_cookies_upload - Stop cookie upload process.\n"
        "Upload cookie files as cookies_<username>.pkl to the bot."
    )





def delete_user(username: str, csv_file_path: str = STATIC_CSV_PATH):
    try:
        if not os.path.exists(csv_file_path):
            print(f"Ошибка: файл {csv_file_path} не найден.")
            return False

        rows = []
        proxy_to_delete = None
        with open(csv_file_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row["username"] == username:
                    proxy_to_delete = row["proxy"]
                else:
                    rows.append(row)

        if not proxy_to_delete:
            print(f"Пользователь {username} не найден в {csv_file_path}.")
            return False

        with open(csv_file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["username", "password", "question", "proxy"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Пользователь {username} удалён из {csv_file_path}.")

        cookie_file_path = os.path.join(COOKIES_DIR, f"cookies_{username}.pkl")
        if os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            print(f"Cookie файл {cookie_file_path} успешно удалён.")
        else:
            print(f"Cookie файл {cookie_file_path} не найден.")

        try:
            proxy_ip = proxy_to_delete.split(":")[0] 
            proxy_file_path = os.path.join(PROXY_EXT_DIR, f"proxys/proxy_auth_plugin_{proxy_ip}.zip")
            if os.path.exists(proxy_file_path):
                os.remove(proxy_file_path)
                print(f"Прокси-расширение {proxy_file_path} успешно удалено.")
            else:
                print(f"Прокси-расширение {proxy_file_path} не найдено.")
        except Exception as e:
            print(f"Ошибка при удалении прокси-расширения: {e}")

        return True

    except Exception as e:
        print(f"Ошибка при удалении пользователя {username}: {e}")
        return False
    
async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 1:
            await update.message.reply_text(
                "Пожалуйста, укажите имя пользователя. Пример:\n/delete_user user123"
            )
            return

        username = context.args[0]

        success = delete_user(username)

        if success:
            await update.message.reply_text(f"Пользователь {username} успешно удалён.")
        else:
            await update.message.reply_text(f"Ошибка: пользователь {username} не найден или произошла ошибка.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():

    TOKEN = "7073437155:AAFcIB3hjjq4zgbQ8S59Jtn2po-1Iak7oQA"


    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("run", run_function))
    application.add_handler(CommandHandler("setinterval", set_interval))
    application.add_handler(CommandHandler("cancel", cancel_schedule))
    application.add_handler(CommandHandler("showcsv", show_csv))
    application.add_handler(CommandHandler("delete_user", delete_user_command))
    application.add_handler(CommandHandler("create_users_batch", create_users_batch))
    application.add_handler(CommandHandler("stop_cookies_upload", stop_cookies_upload))

    
    application.add_handler(MessageHandler(
        filters.Document.FileExtension("csv") & filters.ChatType.PRIVATE,
        create_users_batch
    ))
    application.add_handler(MessageHandler(
        filters.Document.FileExtension("pkl") & filters.ChatType.PRIVATE,
        handle_cookies_upload
    ))
    print("Бот запущен.")
    application.run_polling()

if __name__ == "__main__":
    main()
