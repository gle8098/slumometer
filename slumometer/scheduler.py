from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from datetime import timedelta
from datetime import time
from common import MOSCOW_TIMEZONE
import logging

LOG = logging.getLogger("slumometer.scheduler")
LOG.addHandler(logging.StreamHandler())
LOG.setLevel(logging.INFO)

_JOB_ADMIN_NOTIFIER = 'admin_notifier'  # A job that reminds admin to set new datetime for linen change
_JOB_USER_NOTIFIER = 'user_notifier'  # The main job which sends notifications to users
_FIRST_ADMIN_NOTIFICATION_DELAY = timedelta(days=14)
_PERIODICAL_ADMIN_NOTIFICATION_DELAY = timedelta(days=7)
# Времена, в которые можно присылать уведомления. (за исключением 1-часовой зоны перед концом смены)
# Указаны в московской временной зоне
_USER_NOTIFICATION_TIMES_TO_SEND = (
    time(8, 0),
    time(8, 55),
    time(10, 50),
    time(12, 15),
    time(13, 50),
    time(15, 25),
    time(17, 0),
    time(18, 30),
    time(20, 0)
)

USER_NOTIFY_TYPE_USUAL = 1
USER_NOTIFY_TYPE_1HOUR_TO_END = 2
USER_NOTIFY_TYPE_30MIN_TO_END = 3
USER_NOTIFY_TYPE_15MIN_TO_END = 4
USER_NOTIFY_TYPE_LAST = 5

_USER_ENDING_ZONE        = timedelta(hours=1, minutes=30)
_USER_1HOUR_TO_END_DELAY = timedelta(hours=1)
_USER_30MIN_TO_END_DELAY = timedelta(minutes=30)
_USER_15MIN_TO_END_DELAY = timedelta(minutes=15)

_scheduler = None
_storage = None
_callback = None


# Returns: (NOTIFY_TYPE, datetime for next alarm)
def _find_next_time_to_notify_user(cur_datetime, to_datetime):
    time_remaining = to_datetime - cur_datetime
    if time_remaining <= _USER_ENDING_ZONE:
        if time_remaining < _USER_15MIN_TO_END_DELAY:
            return USER_NOTIFY_TYPE_LAST, to_datetime
        if time_remaining < _USER_30MIN_TO_END_DELAY:
            return USER_NOTIFY_TYPE_15MIN_TO_END, (to_datetime - _USER_15MIN_TO_END_DELAY)
        if time_remaining < _USER_1HOUR_TO_END_DELAY:
            return USER_NOTIFY_TYPE_30MIN_TO_END, (to_datetime - _USER_30MIN_TO_END_DELAY)
        return USER_NOTIFY_TYPE_1HOUR_TO_END, (to_datetime - _USER_1HOUR_TO_END_DELAY)

    moscow_ending_date = to_datetime.astimezone(MOSCOW_TIMEZONE).date()
    for moscow_send_time in _USER_NOTIFICATION_TIMES_TO_SEND:
        moscow_send_datetime = MOSCOW_TIMEZONE.localize(datetime.combine(moscow_ending_date, moscow_send_time))
        send_datetime = moscow_send_datetime.astimezone(None)

        if send_datetime.replace(tzinfo=None) > cur_datetime:
            return USER_NOTIFY_TYPE_USUAL, send_datetime

    # We shouldn't be here
    LOG.warning("_find_next_time_to_notify_user didn't find a proper next datetime alarm")
    LOG.warning("Cur datetime: {}, to datetime: {}".format(cur_datetime, to_datetime))
    return USER_NOTIFY_TYPE_LAST, to_datetime


def init(storage):
    global _scheduler, _storage
    _storage = storage
    _scheduler = BackgroundScheduler()
    _scheduler.add_jobstore('sqlalchemy', url=storage.get_scheduler_db_url())
    _scheduler.start()


def init_for_test(storage):
    global _FIRST_ADMIN_NOTIFICATION_DELAY, _PERIODICAL_ADMIN_NOTIFICATION_DELAY
    _FIRST_ADMIN_NOTIFICATION_DELAY = timedelta(minutes=2)
    _PERIODICAL_ADMIN_NOTIFICATION_DELAY = timedelta(minutes=1)

    global _USER_1HOUR_TO_END_DELAY, _USER_15MIN_TO_END_DELAY, _USER_30MIN_TO_END_DELAY, _USER_ENDING_ZONE
    _USER_1HOUR_TO_END_DELAY = timedelta(seconds=60*3)
    _USER_30MIN_TO_END_DELAY = timedelta(seconds=60*2)
    _USER_15MIN_TO_END_DELAY = timedelta(seconds=60)
    _USER_ENDING_ZONE = timedelta(seconds=60*5)

    global _USER_NOTIFICATION_TIMES_TO_SEND
    _USER_NOTIFICATION_TIMES_TO_SEND = (
        time(3, 45),
        time(3, 47),
        time(3, 49),
        time(3, 51),
        time(3, 53),
        time(3, 55),
        time(3, 57),
        time(3, 59),
        time(4, 1),
    )

    init(storage)


def shutdown():
    if _scheduler is not None:
        _scheduler.shutdown()


def _on_event_trigger(job_name, **kwargs):
    if job_name == _JOB_ADMIN_NOTIFIER:
        _callback.on_admin_remind()
    elif job_name == _JOB_USER_NOTIFIER:
        #is_last_call = _scheduler.get_job(job_name) is None  # Job is deleted from scheduler if it's the last call
        #_callback.on_user_notification(kwargs['is_first'], is_last_call)
        #if kwargs['is_first']:
        #    kwargs['is_first'] = False
        #    _scheduler.modify_job(job_name, kwargs=kwargs)
        #if is_last_call:
        #    # Reset time_next_change in storage
        #    clear_time_next_change()

        alarm_type = kwargs['type']
        next_alarm_datetime = None

        if type == USER_NOTIFY_TYPE_LAST:
            clear_time_next_change()
        else:
            params = _set_next_user_notification_job(False)
            next_alarm_datetime = params[1]

        _callback.on_user_notification(alarm_type, next_alarm_datetime, kwargs['is_first'])


def set_callback(callback):
    global _callback
    _callback = callback


def _set_job(job_name, *args, **kwargs):
    if _scheduler.get_job(job_name) is not None:
        _scheduler.remove_job(job_name)

    job_args = [job_name]
    job_args.extend(kwargs['args'] if 'args' in kwargs else [])
    kwargs['args'] = job_args
    kwargs['id'] = job_name
    _scheduler.add_job(_on_event_trigger, *args, **kwargs)


def _set_next_user_notification_job(is_first_alarm):
    start_alarms_datetime = datetime.fromtimestamp(_storage.time_next_change[0])
    hacked_current_time = max(datetime.now(), start_alarms_datetime - timedelta(seconds=1))  # Вычитаем секунду, так как
    # _find_next_time_to_notify_user сравнивает строгим порядком

    next_notify_params = _find_next_time_to_notify_user(hacked_current_time,
                                                        datetime.fromtimestamp(_storage.time_next_change[1]))
    _set_job(_JOB_USER_NOTIFIER, 'date', run_date=next_notify_params[1], kwargs={'type': next_notify_params[0],
                                                                                 'is_first': is_first_alarm})
    return next_notify_params


def clear_time_next_change():
    if _scheduler.get_job(_JOB_USER_NOTIFIER) is not None:
        _scheduler.remove_job(_JOB_USER_NOTIFIER)
    _storage.time_next_change = None
    _storage.save()


def update_admin_notification_time(notify_time):
    if type(notify_time) is float:
        # It's timestamp
        notify_time = datetime.fromtimestamp(notify_time)

    _set_job(_JOB_ADMIN_NOTIFIER, 'interval', seconds=_PERIODICAL_ADMIN_NOTIFICATION_DELAY.total_seconds(),
             start_date=notify_time)
    _storage.next_admin_notification_time = notify_time.timestamp()
    _storage.save()


# Returns datetime of first alarm
def update_time_of_next_change(time_next_change):
    # First set new admin notification date
    user_alarm_datetime = datetime.fromtimestamp(time_next_change[0])
    admin_alarm_datetime = user_alarm_datetime + _FIRST_ADMIN_NOTIFICATION_DELAY
    update_admin_notification_time(admin_alarm_datetime)

    # Now save the storage
    _storage.time_next_change = time_next_change
    _storage.save()

    # Set user job
    notif_params = _set_next_user_notification_job(True)

    return notif_params[1]


class Callback:
    def on_admin_remind(self):
        pass

    def on_user_notification(self, alarm_type, next_alarm_datetime, is_first_alarm):
        pass
