            return {"error": "Shop not found", "shop_id": shop_id}, 404
    except Exception as e:
        return {"error": "Failed to retrieve shop data", "details": str(e)}, 500

# Mount static asset folders for both Next.js (_next) and Vite (assets)
# Shop logos are stored under static/logos and must be publicly readable by
# customer storefronts. The profile API still controls which logo belongs to
# which authenticated owner.
static_root = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_root, exist_ok=True)
api.mount("/static", StaticFiles(directory=static_root), name="static")

frontend_web_out = os.path.join(os.path.dirname(__file__), "frontend-web", "out")
frontend_vite_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")

next_assets_path = os.path.join(frontend_web_out, "_next")
if os.path.exists(next_assets_path):
    api.mount("/_next", StaticFiles(directory=next_assets_path), name="next_assets")

vite_assets_path = os.path.join(frontend_vite_dist, "assets")
if os.path.exists(vite_assets_path):
    api.mount("/assets", StaticFiles(directory=vite_assets_path), name="vite_assets")


@api.get("/dashboard", tags=["Web UI"])
async def serve_dashboard(request: Request):