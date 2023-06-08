from quart import Blueprint, Quart, render_template, redirect, url_for, request, session, flash, session
from quart_discord import DiscordOAuth2Session

def init_blueprint(discord):
    epmain = Blueprint("epmain", __name__)

    @epmain.route("/", methods=["GET", "POST"])
    async def home():
        if(request.method == "POST"):
            channel = request.form.get("channelid")
            message = request.form.get("message")
            return(redirect(url_for("epmain.home")))
        return(
            await render_template(
                "index.html", 
                title="Home"
            )
        )

    @epmain.route("/Login")
    async def login():
        return(
            await discord.create_session()
        )

    @epmain.route("/Callback")
    async def callback():
        try:
            await discord.callback()
        except:
            flash("Login failed.", "red")
            return(redirect(url_for("epmain.login")))
        
        user = await discord.fetch_user()
        returnf("{user.name}#{user.discriminator}")
    
    return(epmain)