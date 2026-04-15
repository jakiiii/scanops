from datetime import datetime


def user_photo_directory_path(instance, filename):
    _datetime = datetime.now()
    datetime_str_dir = _datetime.strftime("%Y-%m-%d")
    datetime_str_name = _datetime.strftime("%Y-%m-%d-%H-%M-%S")
    file_name_split = filename.split('.')
    file_name_list = file_name_split[:-1]
    ext = file_name_split[-1]
    file_name_wo_ext = '.'.join(file_name_list)
    return "users/{0}/{1}-{2}.{3}".format(datetime_str_dir, file_name_wo_ext, datetime_str_name, ext)
