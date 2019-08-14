import telebot
import sys
import logging
from slumometer import storage, scheduler, localization as loc
from datetime import datetime
from pytz import timezone

MOSCOW_TIMEZONE = timezone('Europe/Moscow')
LOG = logging.getLogger("slumometer.bot")
LOG.addHandler(logging.StreamHandler())
LOG.setLevel(logging.INFO)

if len(sys.argv) < 2 and __name__ == '__main__':
    print("Error! Secret token of the bot is not given. Please, run this bot as follows:")
    print("python3 bot.py <SECRET_TOKEN> [ADMIN_KEY]")
    print("ADMIN_KEY is 11235 by default")
    sys.exit(1)
bot_token = sys.argv[1]
admin_key = sys.argv[2] if len(sys.argv) > 2 else '11235'

bot = telebot.TeleBot(bot_token)
storage = storage.Storage()


def _to_printable_datetime(timestamp, **kwargs):
    if timestamp is None:
        return loc.NA
    date_format = ''
    if 'no_date' not in kwargs:
        date_format += '%d.%m.%Y '
    if 'no_time' not in kwargs:
        date_format += '%H:%M '
    date_format = date_format[:-1]  # Cut the last space
    return datetime.fromtimestamp(timestamp).astimezone(MOSCOW_TIMEZONE).strftime(date_format)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(msg):
    bot.send_message(msg.chat.id, loc.HELLO_MESSAGE)


@bot.message_handler(commands=['subscribe'])
def subscribe(msg):
    chat_id = msg.chat.id
    if chat_id in storage.subscribed_chats:
        bot.send_message(chat_id, loc.ALREADY_SUBSCRIBED)
        return
    storage.subscribed_chats.append(chat_id)
    storage.save()
    bot.send_message(chat_id, loc.SUBSCRIBE_MESSAGE)


@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(msg):
    chat_id = msg.chat.id
    if chat_id not in storage.subscribed_chats:
        bot.send_message(chat_id, loc.NOT_SUBSCRIBED)
        return
    storage.subscribed_chats.remove(chat_id)
    storage.save()
    bot.send_message(chat_id, loc.UNSUBSCRIBE_MESSAGE)


@bot.message_handler(commands=['admin'])
def add_admin(msg):
    space_index = msg.text.find(' ')
    key = msg.text[space_index+1:] if space_index != -1 else ''
    if not key:
        bot.send_message(msg.chat.id, loc.ADMIN_COMMAND_ABOUT)
    elif key == admin_key:
        if msg.chat.id in storage.admin_chats:
            bot.send_message(msg.chat.id, loc.ALREADY_ADMIN_MESSAGE)
        else:
            storage.admin_chats.append(msg.chat.id)
            storage.save()
            bot.send_message(msg.chat.id, loc.ADMIN_ADDED_MESSAGE)
    else:
        bot.send_message(msg.chat.id, loc.WRONG_ADMIN_KEY_MESSAGE)


@bot.message_handler(commands=['unadmin'])
def remove_admin(msg):
    if msg.chat.id not in storage.admin_chats:
        bot.send_message(msg.chat.id, loc.ADMIN_ONLY_USAGE)
    else:
        storage.admin_chats.remove(msg.chat.id)
        storage.save()
        bot.send_message(msg.chat.id, loc.ADMIN_REMOVED_MESSAGE)


@bot.message_handler(commands=['stc'])
def set_time_change(msg):
    if msg.chat.id not in storage.admin_chats:
        bot.send_message(msg.chat.id, loc.ADMIN_ONLY_USAGE)
        return

    args = msg.text.split(' ')

    if len(args) == 2 and args[1] == "n/a":
        scheduler.clear_time_next_change()
        bot.send_message(msg.chat.id, loc.TIME_NEXT_CHANGE_CLEARED)
        return

    if len(args) != 4:
        bot.send_message(msg.chat.id, loc.ABOUT_SET_TIME_CHANGE_COMMAND)
        return

    try:
        format_type = '%Y-%m-%d %H:%M'
        time_start = MOSCOW_TIMEZONE.localize(datetime.strptime('{} {}'.format(args[1], args[2]), format_type)) \
            .timestamp()
        time_end = MOSCOW_TIMEZONE.localize(datetime.strptime('{} {}'.format(args[1], args[3]), format_type)) \
            .timestamp()
    except ValueError:
        bot.send_message(msg.chat.id, loc.BAD_DATETIME_MESSAGE)
        return
    if time_end < time_start or datetime.now().timestamp() > time_start:
        bot.send_message(msg.chat.id, loc.BAD_DATETIME_MESSAGE)
        return

    scheduler.update_time_of_next_change([time_start, time_end])
    bot.send_message(msg.chat.id, loc.TIME_NEXT_CHANGE_UPDATED.format(_to_printable_datetime(time_start)))


@bot.message_handler(commands=['status'])
def send_status(msg):
    time_next_change = storage.time_next_change
    time_starts = _to_printable_datetime(time_next_change[0]) if time_next_change is not None else loc.NA
    time_ends = _to_printable_datetime(time_next_change[1]) if time_next_change is not None else loc.NA
    if msg.chat.id in storage.admin_chats:
        time_admin_notify = _to_printable_datetime(storage.next_admin_notification_time)
        bot.send_message(msg.chat.id, loc.ADMIN_STATUS_MESSAGE.format(time_starts, time_ends, time_admin_notify),
                     parse_mode="Markdown")
    else:
        bot.send_message(msg.chat.id, loc.STATUS_MESSAGE.format(time_starts, time_ends), parse_mode="Markdown")


@bot.message_handler(commands=['linen_changed'])
def update_chat_with_changed_linen(msg):
    if msg.chat.id in storage.chats_to_notify:
        storage.chats_to_notify.remove(msg.chat.id)
        storage.save()
        bot.send_message(msg.chat.id, loc.LINEN_CHANGED_MESSAGE)
    else:
        bot.send_message(msg.chat.id, loc.LINEN_ALREADY_CHANGED_MESSAGE)


@bot.message_handler(commands=['sant'])
def set_admin_notification_time(msg):
    if msg.chat.id not in storage.admin_chats:
        bot.send_message(msg.chat.id, loc.ADMIN_ONLY_USAGE)
        return

    args = msg.text.split(' ')
    if len(args) < 2 or len(args) > 3:
        bot.send_message(msg.chat.id, loc.ABOUT_SET_ADMIN_NOTIFICATION_TIME)
        return

    try:
        date = args[1]
        time = args[2] if len(args) > 2 else '12:00'
        notify_time = MOSCOW_TIMEZONE.localize(datetime.strptime('{} {}'.format(date, time), '%Y-%m-%d %H:%M'))\
            .timestamp()
    except ValueError:
        bot.send_message(msg.chat.id, loc.BAD_DATETIME_MESSAGE)
        return
    if datetime.now().timestamp() > notify_time:
        bot.send_message(msg.chat.id, loc.BAD_DATETIME_MESSAGE)
        return

    scheduler.update_admin_notification_time(notify_time)
    bot.send_message(msg.chat.id, loc.ADMIN_NOTIFICATION_TIME_CHANGED.format(_to_printable_datetime(notify_time)),
                 parse_mode="Markdown")


class EventHandler(scheduler.Callback):
    def on_admin_remind(self):
        for chat_id in storage.admin_chats:
            bot.send_message(chat_id, loc.ADMIN_NOTIFY_SET_NEXT_TIME.format(
                _to_printable_datetime(storage.next_admin_notification_time, no_time=True)), parse_mode="Markdown")

    def on_user_notification(self, is_first_call, is_last_call):
        if is_first_call:
            # Reset storage.chats_to_notify
            storage.chats_to_notify = storage.subscribed_chats.copy()
            storage.save()
        text = loc.NOTIFY_LINEN_CHANGE.format(_to_printable_datetime(storage.time_next_change[1], no_date=True))\
            if not is_last_call else loc.NOTIFY_LAST_LINEN_CHANGE
        for chat_id in storage.chats_to_notify:
            bot.send_message(chat_id, text)


if __name__ == '__main__':
    storage.load()
    scheduler.set_callback(EventHandler())
    scheduler.init(storage)

    LOG.info('Starting bot')
    telebot.logger.setLevel(logging.INFO)

    bot.polling(True)
