from quart import Quart
from quart_discord import DiscordOAuth2Session
from dotenv import load_dotenv
import os

load_dotenv()

def start():
    app = Quart(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
    app.config["SERVER_NAME"] = "localhost:5000"
    app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
    app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
    app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")

    from .epmain import init_blueprint

    discord = DiscordOAuth2Session(app)
    blueprint = init_blueprint(discord)
    app.register_blueprint(blueprint)

    return(app, discord)
