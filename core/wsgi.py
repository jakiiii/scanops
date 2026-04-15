from django.core.wsgi import get_wsgi_application
from core.env import configure_environment


configure_environment()

application = get_wsgi_application()
