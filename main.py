#!/usr/bin/python3
import json
import os
import re
import threading
import traceback
import urllib.request
from multiprocessing import Process
from urllib.request import urlopen, urlretrieve

import telebot
import vk_api

PATH_TO_CONFIG = os.path.dirname(os.path.abspath(__file__)) + "/config.json"


def update_config(config):
    config["all_ids"] = list(config["all_ids"])
    with open(PATH_TO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f)


CONFIG = json.load(open(PATH_TO_CONFIG, encoding="utf-8"))

REQUIRED_FIELDS = [
    "telegram_token",
    "vk_phone",
    "vk_password",
    "working_directory",
    "start_message",
    "help_message",
    "group_id",
    "stop_message",
]

if not all(field in CONFIG.keys() for field in REQUIRED_FIELDS):
    raise KeyError("Check required fields in CONFIG file")

if not "all_ids" in CONFIG.keys():
    CONFIG["all_ids"] = set()
    update_config(CONFIG)
else:
    CONFIG["all_ids"] = set(CONFIG["all_ids"])
if not "last_id" in CONFIG.keys():
    CONFIG["last_id"] = -1
    update_config(CONFIG)

BOT = telebot.TeleBot(CONFIG["telegram_token"])

VK_SESSION = vk_api.VkApi(CONFIG["vk_phone"], CONFIG["vk_password"])
VK_SESSION.auth()

VK = VK_SESSION.get_api()

if not os.path.isfile(CONFIG["working_directory"] + "/log.txt"):
    open(CONFIG["working_directory"] + "/log.txt", "x")


def write_log(info):
    with open(CONFIG["working_directory"] + "/log.txt", "a") as f:
        f.write(str(traceback.format_exc()) + "\n" + str(info) + "\n\n")


@BOT.channel_post_handler(commands=["start"])
def start_chanel(message):
    global CONFIG
    CONFIG["all_ids"].add(message.chat.id)
    update_config(CONFIG)
    BOT.reply_to(
        message, CONFIG["start_message"],
    )


@BOT.message_handler(commands=["start"])
def start_private(message):
    global CONFIG
    CONFIG["all_ids"].add(message.chat.id)
    update_config(CONFIG)
    BOT.reply_to(
        message, CONFIG["start_message"],
    )


@BOT.message_handler(commands=["help"])
def help_private(message):
    global CONFIG
    BOT.reply_to(message, CONFIG["help_message"])


@BOT.channel_post_handler(commands=["help"])
def help_channel(message):
    global CONFIG
    BOT.reply_to(message, CONFIG["help_message"])


@BOT.message_handler(commands=["stop"])
def stop_private(message):
    global CONFIG
    try:
        CONFIG["all_ids"].remove(message.chat.id)
        update_config(CONFIG)
    except ValueError as error:
        pass
    except Exception as error:
        write_log(error)
    BOT.reply_to(message, CONFIG["stop_message"])


@BOT.channel_post_handler(commands=["stop"])
def stop_channel(message):
    global CONFIG
    try:
        CONFIG["all_ids"].remove(message.chat.id)
        update_config(CONFIG)
    except ValueError as error:
        pass
    except Exception as error:
        write_log(error)
    BOT.reply_to(message, CONFIG["stop_message"])


TO_SEND_FILES = []


def download(url):
    global CONFIG
    global TO_SEND_FILES
    page = urlopen(url)
    content = page.read()
    page.close()
    link = content.decode("utf-8", "ignore")
    string = re.compile('<source src=\\"([^"]*)\\"')
    urls = string.findall(link)
    for i in ["1080.mp4", "720.mp4", "360.mp4", "240.mp4"]:
        for uri in urls:
            if i in uri:
                source = uri.replace("\\/", "/")
                reg = re.compile(r"/([^/]*\.mp4)")
                name = reg.findall(source)[0]
                path = CONFIG["working_directory"] + "/tmp/"
                if not os.path.exists(path):
                    os.makedirs(path)
                fullpath = os.path.join(path, name)
                urlretrieve(source, fullpath)
                TO_SEND_FILES.append(fullpath)
                return


def post(response):
    global CONFIG
    attachments = response["attachments"]
    number = 1
    for attachment in attachments:
        if attachment["type"] == "photo":
            url = (
                "https://vk.com/photo"
                + str(attachment["photo"]["owner_id"])
                + "_"
                + str(attachment["photo"]["id"])
            )
            try:
                max_size = 0
                for size in attachment["photo"]["sizes"]:
                    if max_size < int(size["height"]):
                        url = size["url"]
                        max_size = int(size["height"])
                file_path = (
                    CONFIG["working_directory"] + "/tmp/photo" + str(number) + ".jpg"
                )
                urllib.request.urlretrieve(url, file_path)
                TO_SEND_FILES.append(file_path)
            except Exception:
                write_log(response)
        elif attachment["type"] == "video":
            url = (
                "https://vk.com/video"
                + str(attachment["video"]["owner_id"])
                + "_"
                + str(attachment["video"]["id"])
            )
            download(url)
        elif attachment["type"] == "link":
            pass
        else:
            write_log(response)
        number += 1
    if len(TO_SEND_FILES) > 1:
        media = []
        index = 1
        for i in TO_SEND_FILES:
            if str(i).endswith(".mp4"):
                if index == 1:
                    media.append(
                        telebot.types.InputMediaVideo(
                            open(i, "rb"), caption=str(response["text"])
                        )
                    )
                else:
                    media.append(telebot.types.InputMediaVideo(open(i, "rb")))
            else:
                if index == 1:
                    media.append(
                        telebot.types.InputMediaPhoto(
                            open(i, "rb"), caption=str(response["text"])
                        )
                    )
                else:
                    media.append(telebot.types.InputMediaPhoto(open(i, "rb")))
            index += 1
        for i in CONFIG["all_ids"]:
            BOT.send_media_group(i, media=media)
        del media[:]
    elif str(TO_SEND_FILES[0]).endswith(".mp4"):
        for i in CONFIG["all_ids"]:
            current_file = open(TO_SEND_FILES[0], "rb")
            BOT.send_video(i, current_file, caption=str(response["text"]))
            current_file.close()
    else:
        for i in CONFIG["all_ids"]:
            current_file = open(TO_SEND_FILES[0], "rb")
            BOT.send_photo(i, current_file, caption=str(response["text"]))
            current_file.close()
    for i in TO_SEND_FILES:
        os.remove(i)
    TO_SEND_FILES.clear()


def check():
    global CONFIG
    threading.Timer(20.0, check).start()
    response = VK.wall.get(
        owner_id=CONFIG["group_id"], count="1", filter="owner", extended="1", offset=0
    )
    for item in response["items"]:
        if (
            CONFIG["last_id"] != int(item["id"])
            and item["marked_as_ads"] != 1
            and not item["text"].find("#партнёр") != -1
        ):
            try:
                post(item)
            except Exception:
                write_log(item)
            CONFIG["last_id"] = int(item["id"])
            update_config(CONFIG)


def run():
    BOT.polling()


if __name__ == "__main__":
    P1 = Process(target=run)
    P1.start()
    P2 = Process(target=check)
    P2.start()
    P1.join()
    P2.join()
