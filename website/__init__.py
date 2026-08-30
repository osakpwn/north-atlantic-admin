from flask import Flask
from supabase import create_client, Client
import os

SUPABASE_URL = "https://toxkknnfunjjzomdguhx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRveGtrbm5mdW5qanpvbWRndWh4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4Nzk0MzU5MSwiZXhwIjoyMTAzNTE5NTkxfQ.unyzH-zvtOCnv1i3ykEZiATzUpBW0-7cmOfyIhXQwCM" 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def create_app():
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)
    app.config["SECRET_KEY"] = "34tg3r5t3egffGG43r3frgbbgrbfgt4bGFERGrgb"

    from .views import views

    app.register_blueprint(views, url_prefix="/")

    return app
