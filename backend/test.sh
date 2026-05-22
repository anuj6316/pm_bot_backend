docker exec -it pm_bot-django-web-1 python manage.py shell
from plane_client.client import PlaneClient
client = PlaneClient()
print(client.base_url)  # Should show: http://api:8000
client.list_projects()