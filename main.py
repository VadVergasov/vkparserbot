"""
Main file for this bot.
Copyright (C) 2021 Vadim Vergasov

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import json
import os
import re
import threading
import traceback
from multiprocessing import Process
from urllib.request import urlopen, urlretrieve

import telebot
import vk_api

PATH_TO_CONFIG = os.path.dirname(os.path.abspath(__file__)) + "/config.json"


def update_config(config):
    """
    Updates config.
    """
    config["all_ids"] = list(config["all_ids"])
    with open(PATH_TO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f)


CONFIG = json.load(open(PATH_TO_CONFIG, encoding="utf-8"))

REQUIRED_FIELDS = [
    "telegram_token",
    "vk_token",
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

VK_SESSION = vk_api.VkApi(token=CONFIG["vk_token"])

VK = VK_SESSION.get_api()

if not os.path.isfile(CONFIG["working_directory"] + "/log.txt"):
    open(CONFIG["working_directory"] + "/log.txt", "x")

if not os.path.isdir(CONFIG["working_directory"] + "/tmp"):
    os.mkdir(CONFIG["working_directory"] + "/tmp")


def write_log(info):
    """
    Writing a log.
    """
    with open(CONFIG["working_directory"] + "/log.txt", "a") as f:
        f.write(str(traceback.format_exc()) + "\n" + str(info) + "\n\n")


@BOT.channel_post_handler(commands=["start"])
def start_chanel(message):
    """
    Starting to post in a channel.
    """
    global CONFIG
    CONFIG["all_ids"].add(message.chat.id)
    update_config(CONFIG)
    BOT.reply_to(
        message,
        CONFIG["start_message"],
    )


@BOT.message_handler(commands=["start"])
def start_private(message):
    """
    Starting to post in a private chat.
    """
    global CONFIG
    CONFIG["all_ids"].add(message.chat.id)
    update_config(CONFIG)
    BOT.reply_to(
        message,
        CONFIG["start_message"],
    )


@BOT.message_handler(commands=["help"])
def help_private(message):
    """
    Answering in private chat for a /help command.
    """
    global CONFIG
    BOT.reply_to(message, CONFIG["help_message"])


@BOT.channel_post_handler(commands=["help"])
def help_channel(message):
    """
    Answering in the channel for a /help command.
    """
    global CONFIG
    BOT.reply_to(message, CONFIG["help_message"])


@BOT.message_handler(commands=["stop"])
def stop_private(message):
    """
    Stops posting in private chat.
    """
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
    """
    Stops posting in the channel.
    """
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
    """
    Downloads video from VK by the URL.
    https://github.com/sergei-bondarenko/vk-downloader
    """
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
    """
    Posts a post by the bot.
    """
    global CONFIG
    try:
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
                    file_path = CONFIG["working_directory"] + "/tmp/photo%s.jpg" % str(
                        number
                    )
                    urlretrieve(url, file_path)
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
    except KeyError:
        for i in CONFIG["all_ids"]:
            BOT.send_message(i, response["text"])


def check():
    """
    Checks if there is a new post in the specified group.
    """
    global CONFIG
    threading.Timer(20.0, check).start()
    response = VK.wall.get(
        owner_id=CONFIG["group_id"], count="1", filter="owner", extended="1", offset=0
    )
    try:
        if str(response["items"][0]["is_pinned"]) == "1" and str(
            response["items"][0]["id"]
        ) == str(CONFIG["last_id"]):
            response = VK.wall.get(
                owner_id=CONFIG["group_id"],
                count="1",
                filter="owner",
                extended="1",
                offset=1,
            )
    except KeyError:
        pass
    for item in response["items"]:
        if (
            CONFIG["last_id"] < int(item["id"])
            and item["marked_as_ads"] != 1
            and not item["text"].find("#партнёр") != -1
            and not item["text"].find("#ad") != -1
            and len(re.findall(r"\w+\|\w+", item["text"])) == 0
        ):
            try:
                post(item)
            except Exception:
                write_log(item)
            CONFIG["last_id"] = int(item["id"])
            update_config(CONFIG)


def run():
    """
    Runs the bot.
    """
    BOT.polling()


if __name__ == "__main__":
    P1 = Process(target=run)
    P1.start()
    P2 = Process(target=check)
    P2.start()
    P1.join()
    P2.join()
