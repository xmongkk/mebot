import os

import openai
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from jmisbest.Config import Config
from jmisbest.core.managers import edit_delete, edit_or_reply
from jmisbest.helpers.functions import format_image, wall_download
from jmisbest.helpers.google_tools import chromeDriver
from jmisbest.sql_helper.globals import gvarstatus

openai.api_key = Config.OPENAI_API_KEY
conversations = {}


def generate_gpt_response(input_text, chat_id):
    global conversations
    model = gvarstatus("CHAT_MODEL") or "gpt-3.5-turbo"
    system_message = gvarstatus("SYSTEM_MESSAGE") or None
    messages = conversations.get(chat_id, [])

    # Add system message if it exists
    if system_message and not messages:
        messages.append({"role": "system", "content": system_message})

    # Add the new user message
    messages.append({"role": "user", "content": input_text})
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
        )
        generated_text = response.choices[0].message.content.strip()

        # Save the assistant's response to the conversation history
        messages.append({"role": "assistant", "content": generated_text})
        conversations[chat_id] = messages
    except Exception as e:
        generated_text = f"خطأ في الأستجابة من الذكاء الأسطناعي: {str(e)}"
    return generated_text


def generate_edited_response(input_text, instructions):
    try:
        response = openai.Edit.create(
            model="text-davinci-edit-001",
            input=input_text,
            instruction=instructions,
        )
        edited_text = response.choices[0].text.strip()
    except Exception as e:
        edited_text = (
            f"خطا في الأستجابة للرسالة المعدلة من الذكاء الأسطناعي: `{str(e)}`"
        )
    return edited_text


def del_convo(chat_id, checker=False):
    global conversations
    out_text = "لا يوجد  محتوى من الذكاء الاسطناعي لحذفه"
    # Delete the the context of given chat
    if chat_id in conversations:
        del conversations[chat_id]
        out_text = "تم حذف محتوى الذكاء الاسطناعي لهذه الدردشة"
    if checker:
        return out_text


async def generate_dalle_image(text, reply, event, flag=None):
    size = gvarstatus("DALLE_SIZE") or "1024"
    limit = int(gvarstatus("DALLE_LIMIT") or "1")
    if not text and reply:
        text = reply.text
    if not text:
        return await edit_delete(event, "**- يجب عليك وضع عنوان للصنع اولا**")

    catevent = await edit_or_reply(event, "**- جار صنع الصورة أنتظر قليلا**")
    try:
        if flag:
            filename = "dalle-in.png"
            await event.client.download_media(reply, filename)
            format_image(filename)
            if flag == "e":
                response = openai.Image.create_edit(
                    image=open(filename, "rb"),
                    prompt=text,
                    n=limit,
                    size=f"{size}x{size}",
                )
            elif flag == "v":
                response = openai.Image.create_variation(
                    image=open(filename, "rb"),
                    n=limit,
                    size=f"{size}x{size}",
                )
            os.remove(filename)
        else:
            response = openai.Image.create(
                prompt=text,
                n=limit,
                size=f"{size}x{size}",
            )
    except Exception as e:
        await edit_delete(catevent, f"خطأ في صنع الصورة: {str(e)}")
        return None, None

    photos = []
    captions = []
    for i, media in enumerate(response["data"], 1):
        photo = await wall_download(media["url"], "Dall-E")
        photos.append(photo)
        captions.append("")
        await edit_or_reply(catevent, f"تم التحميل : {i}/{limit}__")

    captions[-1] = f"**➥ العنوان :-** `{text.title()}`"
    await edit_or_reply(catevent, "جار الرفع الان انتظر قليلا  . . .")
    return photos, captions


def ai_response(text):
    driver, error = chromeDriver.start_driver()
    if not driver:
        return error
    driver.get("https://ora.sh/embed/b5034e48-5669-4326-b1a8-75fd91f5fa1e")

    input_box = WebDriverWait(driver, 2).until(
        EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="__next"]/div[2]/div/div/div/div[3]/div/textarea')
        )
    )
    input_box.send_keys(text)
    input_box.send_keys(Keys.ENTER)

    output_box = WebDriverWait(driver, 2).until(
        EC.presence_of_element_located(
            (By.XPATH, '//*[@id="__next"]/div[2]/div/div/div/div[2]/div[2]/div/div/div')
        )
    )
    output_text = ""

    while not output_text:
        try:
            output_text = output_box.text
        except StaleElementReferenceException:
            output_box = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="__next"]/div[2]/div/div/div/div[2]/div[2]/div/div/div',
                    )
                )
            )
    # clean out line numbers
    formated_out = ""
    for item in output_text.splitlines():
        if item.isdigit():
            item = ""
        formated_out += item + "\n"

    return formated_out.replace("\n\n", "\n")
