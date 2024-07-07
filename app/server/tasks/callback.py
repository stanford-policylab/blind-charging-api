from .queue import queue


@queue.task(task_track_started=True, task_time_limit=300, task_soft_time_limit=240)
def callback():
    """A callback function."""
    pass
