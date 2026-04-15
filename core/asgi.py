from django.core.asgi import get_asgi_application
from core.env import configure_environment


configure_environment()

application = get_asgi_application()
