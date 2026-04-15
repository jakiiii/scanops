import os
from datetime import datetime


def images_path_dir(instance, filename):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
    file_name, ext = os.path.splitext(filename)
    return f"images/{date_str}/{file_name}-{time_str}{ext}"
