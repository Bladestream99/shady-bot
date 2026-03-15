import discord
from discord.ext import commands
import json
import os
from datetime import timedelta

TOKEN = os.getenv("TOKEN")
LOG_CHANNEL_ID = 1431399966135291968

DATA_FILE = "moddata.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_user_entry(data, guild_id: int, user_id: int):
    gid = str(guild_id)
    uid = str(user_id)

    data.setdefault(gid, {})
    data[gid].setdefault(uid, {
        "notes": [],
        "warns": [],
        "bans": []
    })
    return data[gid][uid]

def is_mod(ctx):
    p = ctx.author.guild_permissions
    return p.administrator or p.moderate_members or p.kick_members or p.ban_members

async def log_action(guild: discord.Guild, text: str):
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(text)

@bot.event
async def on_ready():
    print(f"Bot ist online als {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Bitte 1-100 angeben.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 {len(deleted)-1} Nachrichten gelöscht.", delete_after=5)

@bot.command()
async def note(ctx, user_id: int, *, text: str):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, user_id)

    entry["notes"].append({
        "mod": str(ctx.author),
        "text": text
    })

    save_data(data)
    await ctx.send(f"📝 Notiz für User-ID `{user_id}` gespeichert.")
    await log_action(ctx.guild, f"📝 NOTE | {ctx.author} -> {user_id} | {text}")

@bot.command()
async def warn(ctx, user_id: int, *, reason: str):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, user_id)

    entry["warns"].append({
        "mod": str(ctx.author),
        "reason": reason
    })

    save_data(data)
    await ctx.send(f"⚠️ Warn für User-ID `{user_id}` gespeichert.")
    await log_action(ctx.guild, f"⚠️ WARN | {ctx.author} -> {user_id} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def banid(ctx, user_id: int, *, reason: str = "—"):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.ban(user, reason=reason)
    except Exception as e:
        return await ctx.send(f"❌ Ban fehlgeschlagen: {e}")

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, user_id)

    entry["bans"].append({
        "mod": str(ctx.author),
        "reason": reason
    })

    save_data(data)
    await ctx.send(f"🔨 User-ID `{user_id}` wurde gebannt.")
    await log_action(ctx.guild, f"🔨 BAN | {ctx.author} -> {user_id} | {reason}")

@bot.command()
async def userlog(ctx, user_id: int):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_data()
    gid = str(ctx.guild.id)
    uid = str(user_id)

    entry = data.get(gid, {}).get(uid)
    if not entry:
        return await ctx.send(f"ℹ️ Keine Einträge für User-ID `{user_id}` gefunden.")

    notes = entry.get("notes", [])
    warns = entry.get("warns", [])
    bans = entry.get("bans", [])

    lines = [f"📁 **Mod-Akte für `{user_id}`**"]

    lines.append(f"\n📝 **Notizen ({len(notes)}):**")
    if notes:
        for i, n in enumerate(notes[-5:], start=max(1, len(notes)-4)):
            lines.append(f"`{i}.` {n['text']} — Mod: {n['mod']}")
    else:
        lines.append("Keine")

    lines.append(f"\n⚠️ **Warns ({len(warns)}):**")
    if warns:
        for i, w in enumerate(warns[-5:], start=max(1, len(warns)-4)):
            lines.append(f"`{i}.` {w['reason']} — Mod: {w['mod']}")
    else:
        lines.append("Keine")

    lines.append(f"\n🔨 **Bans ({len(bans)}):**")
    if bans:
        for i, b in enumerate(bans[-5:], start=max(1, len(bans)-4)):
            lines.append(f"`{i}.` {b['reason']} — Mod: {b['mod']}")
    else:
        lines.append("Keine")

    text = "\n".join(lines)

    if len(text) > 1900:
        text = text[:1900] + "\n..."

    await ctx.send(text)

@bot.command()
async def clearnotes(ctx, user_id: int):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_data()
    gid = str(ctx.guild.id)
    uid = str(user_id)

    if gid in data and uid in data[gid]:
        data[gid][uid]["notes"] = []
        save_data(data)
        await ctx.send(f"🧽 Notizen für `{user_id}` gelöscht.")
        await log_action(ctx.guild, f"🧽 CLEARNOTES | {ctx.author} -> {user_id}")
    else:
        await ctx.send("ℹ️ Keine Daten gefunden.")

bot.run(TOKEN)
