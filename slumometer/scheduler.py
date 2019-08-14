from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from datetime import timedelta

_JOB_ADMIN_NOTIFIER = 'admin_notifier'  # A job that reminds admin to set new datetime for linen change
_JOB_USER_NOTIFIER = 'user_notifier'  # The main job which sends notifications to users
_FIRST_ADMIN_NOTIFICATION_DELAY = timedelta(days=14)
_PERIODICAL_ADMIN_NOTIFICATION_DELAY = timedelta(days=7)
_PERIODICAL_USER_NOTIFICATION_DELAY = timedelta(hours=1)
_scheduler = None
_storage = None
_callback = None


def init(storage):
    global _scheduler, _storage
    _storage = storage
    _scheduler = BackgroundScheduler()
    _scheduler.add_jobstore('sqlalchemy', url=storage.get_scheduler_db_url())
    _scheduler.start()


def init_for_test(storage):
    global _FIRST_ADMIN_NOTIFICATION_DELAY, _PERIODICAL_ADMIN_NOTIFICATION_DELAY, _PERIODICAL_USER_NOTIFICATION_DELAY
    _FIRST_ADMIN_NOTIFICATION_DELAY = timedelta(minutes=2)
    _PERIODICAL_ADMIN_NOTIFICATION_DELAY = timedelta(minutes=1)
    _PERIODICAL_USER_NOTIFICATION_DELAY = timedelta(seconds=20)
    init(storage)


def shutdown():
    if _scheduler is not None:
        _scheduler.shutdown()


def _on_event_trigger(job_name, **kwargs):
    if job_name == _JOB_ADMIN_NOTIFIER:
        _callback.on_admin_remind()
    elif job_name == _JOB_USER_NOTIFIER:
        is_last_call = _scheduler.get_job(job_name) is None  # Job is deleted from scheduler if it's the last call
        _callback.on_user_notification(kwargs['is_first'], is_last_call)
        if kwargs['is_first']:
            kwargs['is_first'] = False
            _scheduler.modify_job(job_name, kwargs=kwargs)
        if is_last_call:
            # Reset time_next_change in storage
            clear_time_next_change()


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


def update_time_of_next_change(time_next_change):
    alarm_datetime = datetime.fromtimestamp(time_next_change[0])
    _set_job(_JOB_USER_NOTIFIER, 'interval', seconds=_PERIODICAL_USER_NOTIFICATION_DELAY.total_seconds(),
             kwargs={'is_first': True}, start_date=alarm_datetime, end_date=datetime.fromtimestamp(time_next_change[1]))

    # Also set new admin notification date
    admin_alarm_datetime = alarm_datetime + _FIRST_ADMIN_NOTIFICATION_DELAY
    update_admin_notification_time(admin_alarm_datetime)

    _storage.time_next_change = time_next_change
    _storage.save()


class Callback:
    def on_admin_remind(self):
        pass

    def on_user_notification(self, is_first_call, is_last_call):
        pass
