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

import config

BOT = telebot.TeleBot(config.token)

VK_SESSION = vk_api.VkApi(config.phone, config.password)
VK_SESSION.auth()

VK = VK_SESSION.get_api()

ALL_IDS = []
LAST_ID = -1

if not os.path.isfile(config.working_directory + "/last.id"):
    with open(os.getcwd() + "/last.id", "w"):
        pass
else:
    with open(config.working_directory + "/last.id", "r") as f:
        LAST_ID = int(f.read())

if not os.path.isfile(config.working_directory + "/chats.json"):
    with open("chats.json", "w"):
        pass
with open(config.working_directory + "/chats.json", "r") as f:
    ALL_IDS = json.loads(f.read())


def write_log(error, info):
    if not os.path.isfile(os.getcwd() + "/log.txt"):
        with open(config.working_directory + "/log.txt", "w"):
            pass
    log = ""
    with open(config.working_directory + "/log.txt", "r") as f:
        log = f.read()
    log += str(traceback.format_exc()) + "\n" + str(info) + "\n\n"
    with open("log.txt", "w") as f:
        f.write(log)


def write_ids():
    global ALL_IDS
    with open(config.working_directory + "/chats.json", "w") as f:
        f.write(json.dumps(ALL_IDS))


@BOT.channel_post_handler(commands=["start", "help"])
def start_chanel(message):
    global ALL_IDS
    ALL_IDS.append(message.chat.id)
    write_ids()
    BOT.reply_to(
        message,
        "Теперь Вы будете получать сообщения о новых записях в сообществе /dev/null во Вконтакте.",
    )


@BOT.message_handler(commands=["start", "help"])
def start(message):
    global ALL_IDS
    ALL_IDS.append(message.chat.id)
    write_ids()
    BOT.reply_to(
        message,
        "Теперь Вы будете получать сообщения о новых записях в сообществе /dev/null во Вконтакте.",
    )


@BOT.message_handler(commands=["stop"])
def stop(message):
    global ALL_IDS
    try:
        ALL_IDS.remove(message.chat.id)
        write_ids()
    except Exception as error:
        pass
    BOT.reply_to(message, "Вы отписаны от рассылки")


TO_SEND_FILE = None


def download(url):
    page = urlopen(url)
    content = page.read()
    page.close()
    link = content.decode("utf-8", "ignore")
    string = re.compile('<source src=\\\\"([^"]*)\\\\"')
    urls = string.findall(link)

    for i in ["1080.mp4", "720.mp4", "360.mp4", "240.mp4"]:
        for uri in urls:
            if i in uri:
                source = uri.replace("\\/", "/")
                reg = re.compile(r"/([^/]*\.mp4)")
                name = reg.findall(source)[0]
                path = os.getcwd() + "/tmp/"
                if not os.path.exists(path):
                    os.makedirs(path)
                fullpath = os.path.join(path, name)
                urlretrieve(source, fullpath)
                global TO_SEND_FILE
                TO_SEND_FILE = open(fullpath, "rb")
                return


def post(response):
    global ALL_IDS
    attachments = response["attachments"]
    for i in attachments:
        if i["type"] != "link":
            url = (
                "https://vk.com/"
                + i["type"]
                + str(i[i["type"]]["owner_id"])
                + "_"
                + str(i[i["type"]]["id"])
            )
            if i["type"] == "photo":
                try:
                    info = VK.photos.get(
                        owner_id=str(i[i["type"]]["owner_id"]),
                        album_id=i[i["type"]]["album_id"],
                        photo_ids=i[i["type"]]["id"],
                        count="1",
                    )
                    for j in info["items"][0]["sizes"]:
                        url = j["url"]
                    urllib.request.urlretrieve(
                        url, config.working_directory + "/tmp/" + i["type"] + ".jpg"
                    )
                    for j in range(len(ALL_IDS)):
                        to_send = open(
                            config.working_directory + "/tmp/" + i["type"] + ".jpg",
                            "rb",
                        )
                        BOT.send_photo(
                            ALL_IDS[j], to_send, caption=str(response["text"])
                        )
                    to_send.close()
                    os.remove(config.working_directory + "/tmp/" + i["type"] + ".jpg")
                except Exception as error:
                    write_log(error, response["items"][i])
            elif i["type"] == "video":
                download(url)
                for j in range(len(ALL_IDS)):
                    with open(
                        config.working_directory + "/" + TO_SEND_FILE.name, "rb"
                    ) as f:
                        BOT.send_video(ALL_IDS[j], f, caption=str(response["text"]))
                path = TO_SEND_FILE.name
                TO_SEND_FILE.close()
                os.remove(path)
        elif i["type"] == "link":
            for j in range(len(ALL_IDS)):
                BOT.send_message(
                    ALL_IDS[j],
                    str(response["text"])
                    + "\n["
                    + str(i["link"]["title"])
                    + "]("
                    + str(i["link"]["url"])
                    + ")",
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
        else:
            write_log(TypeError, response)


def check():
    global LAST_ID
    threading.Timer(20.0, check).start()
    response = VK.wall.get(
        owner_id="-72495085", count="1", filter="owner", extended="1", offset=0
    )
    for i in range(len(response["items"]) - 1, -1, -1):
        if (
            LAST_ID != int(response["items"][0]["id"])
            and response["items"][i]["marked_as_ads"] != 1
            and not response["items"][i]["text"].find("Это #партнёрский пост") != -1
        ):
            try:
                post(response["items"][i])
            except Exception as error:
                write_log(error, response["items"][i])
            LAST_ID = int(response["items"][i]["id"])
            with open(config.working_directory + "/last.id", "w") as f:
                f.write(str(LAST_ID))


def run1():
    BOT.polling()


if __name__ == "__main__":
    P1 = Process(target=run1)
    P1.start()
    P2 = Process(target=check)
    P2.start()
    P1.join()
    P2.join()
