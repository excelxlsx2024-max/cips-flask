import os
from flask import Flask, redirect, url_for, session, request, render_template
from flask_session import Session
import requests
from dotenv import load_dotenv
import sqlite3

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

API_BASE_URL = "https://discord.com/api"
OAUTH_AUTHORIZE_URL = f"{API_BASE_URL}/oauth2/authorize"
OAUTH_TOKEN_URL = f"{API_BASE_URL}/oauth2/token"
USER_API_URL = f"{API_BASE_URL}/users/@me"

@app.route("/")
def home():
    user = session.get("user")
    return render_template("home.html", user=user)

@app.route("/login/")
def login():
    return redirect(
        f"{OAUTH_AUTHORIZE_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )

@app.route("/callback/")
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: Kod alınamadı.", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(OAUTH_TOKEN_URL, data=data, headers=headers)
    r.raise_for_status()
    credentials = r.json()
    access_token = credentials["access_token"]

    user_data = requests.get(
        USER_API_URL,
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()

    user_id = user_data["id"]

    # GUILD nickname çekmek için Bot kullanıyoruz
    bot_headers = {
        "Authorization": f"Bot {os.getenv('DISCORD_BOT_TOKEN')}"
    }

    guild_id = os.getenv("GUILD_ID")
    member_data = requests.get(
        f"https://discord.com/api/guilds/{guild_id}/members/{user_id}",
        headers=bot_headers
    )

    if member_data.status_code == 200:
        nickname = member_data.json().get("nick") or user_data["username"]
    else:
        nickname = user_data["username"]

    session["user"] = {
        "username": f'{user_data["username"]}#{user_data["discriminator"]}',
        "id": user_id,
        "avatar": f'https://cdn.discordapp.com/avatars/{user_id}/{user_data["avatar"]}.png'
    }

    # SQL kaydı (sadece bir kere kaydet)
    with sqlite3.connect("database.db") as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT UNIQUE, username TEXT)")
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, nickname))
            conn.commit()

    return redirect(url_for("home"))

@app.route("/logout/")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True)
