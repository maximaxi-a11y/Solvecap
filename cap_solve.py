from random import uniform
import time
import base64
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

driver = webdriver.Chrome()




def solve_cap(driv,usr):
    driver = driv
    screenshot_path = f"full_page_screenshot{usr}.png"
    driver.save_screenshot(screenshot_path)

    wait = WebDriverWait(driver, uniform(3,5))

    
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

    screenshot_path = f"full_page_after{usr}.png"
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
