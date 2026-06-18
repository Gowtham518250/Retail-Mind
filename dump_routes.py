import os
os.environ['DATABASE_URL'] = 'postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog'

from app import api
from fastapi.routing import APIRoute

routes_info = []
for route in api.routes:
    if isinstance(route, APIRoute):
        methods = list(route.methods)
        routes_info.append(f"{methods[0]} {route.path}")

with open('routes_dump.txt', 'w') as f:
    f.write('\n'.join(routes_info))
print(f"Dumped {len(routes_info)} routes to routes_dump.txt")
