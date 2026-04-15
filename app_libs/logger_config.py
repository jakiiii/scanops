"""
 Version: 1.0.0
 Author: Abdullah Al Mohin Jaki
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

__all__ = ["LOGGING"]

# checking log folder has exists or not if not create the log folder
path = BASE_DIR + "/app_logs"
if not os.path.exists(path):
    os.makedirs(path)

# LOG SETUP #
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
        'debug_file': {
            'level': 'DEBUG',
            'filename': os.path.join(BASE_DIR, 'app_logs/django_debug.log'),
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'when': 'MIDNIGHT',
            'formatter': 'main_formatter'
        },
        'general_file': {
            'level': 'DEBUG',
            'filename': os.path.join(BASE_DIR, 'app_logs/app_general.log'),
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'when': 'MIDNIGHT',
            'formatter': 'main_formatter'
        },
        'exceptions_file': {
            'level': 'DEBUG',
            'filename': os.path.join(BASE_DIR, 'app_logs/exceptions.log'),
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'when': 'MIDNIGHT',
            'formatter': 'main_formatter'
        },
    },
    'formatters': {
        'main_formatter': {
            'format': '%(levelname)s | %(asctime)s | %(filename)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s',
            'datefmt': "%Y-%m-%d %H:%M:%S",
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'debug_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django.utils.autoreload': {
            'handlers': ['debug_file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['debug_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'general': {
            'handlers': ['general_file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'exceptions_log': {
            'handlers': ['exceptions_file'],
            'level': 'DEBUG',
            'propagate': True,
        },

        'django.template': {
            'handlers': ['debug_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'parso': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
# LOG SETUP END #

# --- Runtime safety: in containerized environments, prefer console logging or fall back to console
import os as _os

# If explicit container logging requested, route all loggers to console only
if _os.environ.get('JTRO_CONTAINER_LOGS', 'False') == 'True':
    for _lg in LOGGING.get('loggers', {}):
        LOGGING['loggers'][_lg]['handlers'] = ['console']
else:
    # Validate file handlers: if any file handler's file is unwritable, replace file handlers with console fallback
    _bad_handlers = []
    for _hname, _h in list(LOGGING.get('handlers', {}).items()):
        _fname = _h.get('filename')
        if _fname:
            try:
                _d = _os.path.dirname(_fname)
                if not _os.path.exists(_d):
                    _os.makedirs(_d, exist_ok=True)
                # try opening the file for append
                with open(_fname, 'a'):
                    pass
            except Exception:
                _bad_handlers.append(_hname)
    if _bad_handlers:
        # remove problematic handlers and replace them by console in all loggers
        for _bh in _bad_handlers:
            LOGGING['handlers'].pop(_bh, None)
        for _lg_name, _lg_conf in LOGGING.get('loggers', {}).items():
            _handlers = _lg_conf.get('handlers', [])
            # if any handler in this logger was bad, replace the whole handler list with console
            if any(_h in _bad_handlers for _h in _handlers):
                LOGGING['loggers'][_lg_name]['handlers'] = ['console']
        # ensure at least console is present for every logger
        for _lg_name, _lg_conf in LOGGING.get('loggers', {}).items():
            if not _lg_conf.get('handlers'):
                LOGGING['loggers'][_lg_name]['handlers'] = ['console']
