import json
import os
import logging

# This storage keeps bot-related parameters such as admin chats or subscribed users


class Storage:
    _STORAGE_FOLDER = 'data'
    _STORAGE_JSON = 'storage.json'
    _STORAGE_SCHEDULER_DB = 'jobs.sqlite'

    @staticmethod
    def _create_storage_folder_if_needed():
        os.makedirs(Storage._STORAGE_FOLDER, exist_ok=True)

    @staticmethod
    def get_scheduler_db_url():
        Storage._create_storage_folder_if_needed()
        return 'sqlite:///' + os.path.join(Storage._STORAGE_FOLDER, Storage._STORAGE_SCHEDULER_DB)

    @staticmethod
    def _get_storage_json_path():
        return os.path.join(Storage._STORAGE_FOLDER, Storage._STORAGE_JSON)

    subscribed_chats = []
    chats_to_notify = []  # Subscribed chats except those who already changed linen.
    # It should be reset before the day of change
    admin_chats = []
    time_next_change = None  # Date and time of next linen change. An array of timestamps. [time_starts, time_ends].
    # The bot will send notifications every hour beginning from time_starts until time_ends.
    next_admin_notification_time = None  # Timestamp when admins should receive next notification

    _FIELDS = ('subscribed_chats', 'chats_to_notify', 'admin_chats', 'time_next_change', 'next_admin_notification_time')
    # All fields of Storage

    def load(self):
        Storage._create_storage_folder_if_needed()
        try:
            with open(Storage._get_storage_json_path(), 'r') as file:
                data = json.load(file)
                for field in Storage._FIELDS:
                    if field in data:
                        setattr(self, field, data[field])
        except FileNotFoundError:
            logging.getLogger("slumometer.storage").warning("File {0} not found. You should set the time of next linen "
                                                         "change.".format(Storage._STORAGE_JSON))

    # Remember to save the storage after any change
    def save(self):
        Storage._create_storage_folder_if_needed()
        with open(Storage._get_storage_json_path(), 'w') as file:
            data_object = {}
            for field in Storage._FIELDS:
                data_object[field] = getattr(self, field)
            json.dump(data_object, file)
