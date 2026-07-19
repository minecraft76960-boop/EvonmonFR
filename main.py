import discord
import chat_exporter
import io
import json
import os
from discord import app_commands
from discord.ext import commands

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Le bot est en ligne !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
    
# --- CONFIGURATION ---
TOKEN = os.environ.get('TOKEN')
ROLE_STAFF_ID = 1527773468110618815
CATEGORIE_TICKET_ID = 1528078675797606501
LOGS_CHANNEL_ID = 1528183010447462420
LEVEL_CHANNEL_ID = 1528190896661598442
XP_FILE = "xp_data.json"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FONCTIONS XP ---
def load_xp():
    if not os.path.exists(XP_FILE): return {}
    with open(XP_FILE, "r") as f: return json.load(f)

def save_xp(data):
    with open(XP_FILE, "w") as f: json.dump(data, f, indent=4)

# --- SYSTÈME DE TICKETS ---
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="BUG", value="bug", emoji="🐛"),
            discord.SelectOption(label="Amélioration", value="amelioration", emoji="💡"),
            discord.SelectOption(label="Report", value="report", emoji="🚫"),
            discord.SelectOption(label="Questions", value="questions", emoji="❓"),
        ]
        super().__init__(placeholder="Choisis la raison du ticket...", options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        staff_role = guild.get_role(ROLE_STAFF_ID)
        category = guild.get_channel(CATEGORIE_TICKET_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await guild.create_text_channel(name=f"ticket-{interaction.user.name}", category=category, overwrites=overwrites)
        await interaction.response.send_message(f"✅ Ticket créé : {channel.mention}", ephemeral=True)

        view = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
        close_btn.callback = self.close_callback
        view.add_item(close_btn)
        
        embed = discord.Embed(title=f"Sujet : {self.values[0]}", description="Le staff arrive bientôt pour t'aider.", color=discord.Color.blue())
        await channel.send(embed=embed, view=view)

    async def close_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Sauvegarde et fermeture...", ephemeral=True)
        transcript = await chat_exporter.export(interaction.channel)
        if transcript:
            file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript.html")
            logs = interaction.client.get_channel(LOGS_CHANNEL_ID)
            if logs: await logs.send(f"Ticket fermé par {interaction.user.name}", file=file)
        await interaction.channel.delete()

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# --- ÉVÉNEMENTS ---
@bot.event
async def on_ready():
    bot.add_view(TicketView())
    await bot.tree.sync()
    print(f"Connecté en tant que {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot: return
    
    data = load_xp()
    uid = str(message.author.id)
    if uid not in data: data[uid] = {"xp": 0, "lvl": 1}
    
    data[uid]["xp"] += 2 
    
    if data[uid]["xp"] >= data[uid]["lvl"] * 100:
        data[uid]["lvl"] += 1
        data[uid]["xp"] = 0
        save_xp(data)
        
        level_channel = bot.get_channel(LEVEL_CHANNEL_ID)
        if level_channel:
            embed = discord.Embed(
                title="🎉 Félicitations !",
                description=f"{message.author.mention} vient de passer au **niveau {data[uid]['lvl']}** !",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else None)
            await level_channel.send(embed=embed)
    else:
        save_xp(data)
        
    await bot.process_commands(message)

# --- COMMANDES SLASH ---
@bot.tree.command(name="ticket", description="Spawn l'embed de support")
async def ticket(interaction: discord.Interaction):
    icon_url = interaction.guild.icon.url if interaction.guild.icon else None
    embed = discord.Embed(title="🎫 Centre de Support EvomonFR", description="Sélectionne ton motif :", color=discord.Color.orange())
    embed.set_footer(text="Support EvomonFR", icon_url=icon_url)
    await interaction.response.send_message(embed=embed, view=TicketView())

@bot.tree.command(name="xp", description="Voir ton niveau ou celui d'un autre")
async def xp(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    data = load_xp()
    user = data.get(str(target.id), {"xp": 0, "lvl": 1})
    embed = discord.Embed(title=f"Stats de {target.name}", color=discord.Color.green())
    embed.add_field(name="Niveau", value=str(user["lvl"]))
    embed.add_field(name="XP", value=f"{user['xp']} / {user['lvl'] * 100}")
    await interaction.response.send_message(embed=embed)

keep_alive()
bot.run(TOKEN)
