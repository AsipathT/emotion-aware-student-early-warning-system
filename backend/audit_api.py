from fastapi.routing import APIRoute
from app.main import app

def get_route_roles(route: APIRoute):
    roles = "public"
    for d in route.dependencies:
        # FastAPI dependencies are callables. The require_roles closure is wrapped.
        if "require_roles.<locals>._check" in str(d.dependency):
            # This is hard to extract from the closure easily, 
            # we'll just parse the file for exact roles.
            pass
    return roles

print("=== API SURFACE ===")
for r in app.routes:
    if isinstance(r, APIRoute) and r.path.startswith("/api/v1"):
        methods = ",".join(r.methods)
        print(f"{methods} | {r.path} | {r.name}")
