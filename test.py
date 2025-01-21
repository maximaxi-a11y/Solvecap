from random import uniform
import time
import base64
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageDraw
import io
from selenium.webdriver.chrome.options import Options

driver = webdriver.Chrome()

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)

driver.get("""https://market.yandex.ru/showcaptcha?cc=1&mt=0B99279069D1BD4D53411C1C78474D43C245050923FF163FF789F0085F3D79EB0DF11664981C756D60D1550195DD1BA4927B1FF5D9240D2FBB3BC25F8A503D00A6389C4F4B4183366465B8BAB8A55554C80920387071B42106525B104B3F55CBE1D8E46B8EDAAE0E43B2399F4D1EE88B2973DBD429AA7A24CF8375D5C3276D8DA2EBBB7987F2E6FC549803A86CA5E2553943EE3F3D260CD10C75844A4EDD079B7F198736BCE39BCF7726555111F2F9299384DC00FBF4987827B367F48EE63857B182CD89C2DBB281027B4F89C27D1D70EE45C0F84897BA55A9B6B47C9741DF63A3F481B50F322D1D646E1A917449FF5DA2C4CCCC55C5&retpath=aHR0cHM6Ly9tYXJrZXQueWFuZGV4LnJ1Lz8%2C_99b86b0c90a9f4733924eadf32f8714e&t=2/1737401025/740c85bd6133448f9c2b0f5ddc379392&u=5914544705877867687&s=c58b1228debe6c71dbc56f6318a362e2""")

screenshot_path = "full_page_screenshot1.png"
driver.save_screenshot(screenshot_path)

wait = WebDriverWait(driver, uniform(5,7))

captcha_checkbox = wait.until(EC.presence_of_element_located((By.ID, 'js-button')))
time.sleep(uniform(1,3))
captcha_checkbox.click()
time.sleep(uniform(1,2))
captcha_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.AdvancedCaptcha-ImageWrapper')))
captcha_image_url = captcha_element.find_element(By.XPATH, './*').get_attribute("src")

captcha_image_response = requests.get(captcha_image_url)
captcha_image_base64 = base64.b64encode(captcha_image_response.content).decode()

canvas_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.AdvancedCaptcha-SilhouetteTask canvas')))
canvas_screenshot = canvas_element.screenshot_as_png  

task_image_base64 = base64.b64encode(canvas_screenshot).decode()

api_key = "5e82a269e190a9cda98a8238bff4053a" 
api_url_in = "https://2captcha.com/in.php"
payload = {
    "method": "base64",
    "coordinatescaptcha": 1,
    "key": api_key,
    "body": captcha_image_base64,
    "imginstructions": task_image_base64,
    "textinstructions": "Кликните в таком порядке | Click in the following order",
    "json": 1
}

response = requests.post(api_url_in, json=payload)
response_data = response.json()

if response_data.get("status") != 1:
    raise Exception("Ошибка при отправке капчи: " + response_data.get("request"))

captcha_id = response_data["request"]
print(response_data)
print(111111111111111111111111111111111111111111111111111111111111111) 

api_url_res = f"https://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1"
print(api_url_res)

while True:
    response = requests.get(api_url_res)
    response_data = response.json()
    if response_data.get("status") == 1:
        break
    time.sleep(uniform(1,3))

coordinates = response_data["request"]
print(coordinates)
time.sleep(uniform(1,3))

captcha_image_location = captcha_element.location 

captcha_wrapper = driver.find_element(By.CLASS_NAME, "AdvancedCaptcha-ImageWrapper")

driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", captcha_wrapper)

wrapper_location = captcha_wrapper.location
wrapper_size = captcha_wrapper.size

print(f"Контейнер расположен по координатам: {captcha_image_location}")
print(f"Размер контейнера (ширина x высота): {wrapper_size}")


time.sleep(uniform(0.2, 0.5))


for index, coord in enumerate(coordinates, start=1):
    x_offset = int(coord["x"])+int(captcha_image_location['x'])
    y_offset = int(coord["y"])+int(captcha_image_location['y'])

    actions = ActionChains(driver)

    actions.move_by_offset(x_offset, y_offset).click().perform()

    print(f"Клик по смещению: ({x_offset}, {y_offset})")

    actions.move_by_offset(-x_offset, -y_offset).perform()

    time.sleep(uniform(0.5, 1.5))

time.sleep(uniform(0.7, 2)) 

submit_element = WebDriverWait(driver, uniform(1,4)).until(
    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Отправить')]"))
)


submit_element.click()
time.sleep(uniform(3,5))

screenshot_path = "full_page_screenshot.png"
driver.save_screenshot(screenshot_path)
time.sleep(uniform(2,4))
# captcha_screenshot = captcha_element.screenshot_as_png
# captcha_image = Image.open(io.BytesIO(captcha_screenshot))

# captcha_image.save("captcha_with_clicks.png")
# print("Сохранено изображение с кликами: captcha_with_clicks.png")

# time.sleep(un) 

# draw = ImageDraw.Draw(captcha_image)
# for coord in coordinates:
#     x = int(coord["x"])
#     y = int(coord["y"])
#     draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="red", outline="black") 


# captcha_image.save("captcha_with_clicks.png")