import discord
from discord.ext import commands
import json
import os
from datetime import timedelta

TOKEN = "MTQ2OTA1NzExMTY4OTM5NjM4OA.G2f3QY.Mpu9FZuYpIgfOIRhuY8oLBvmiv3BjpsO1COeWk"

# 👉 HIER deine Log-Channel-ID eintragen (Rechtsklick auf Kanal -> "Kanal-ID kopieren")
LOG_CHANNEL_ID = 1431399966135291968

WARN_FILE = "warns.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------
# Helpers
# -------------------------
def load_warns():
    if not os.path.exists(WARN_FILE):
        return {}
    with open(WARN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_warns(data):
    with open(WARN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def log_action(guild: discord.Guild, text: str):
    if LOG_CHANNEL_ID == 0:
        return
    ch = guild.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(text)

def is_mod(ctx: commands.Context) -> bool:
    p = ctx.author.guild_permissions
    return p.administrator or p.moderate_members or p.kick_members or p.ban_members

# -------------------------
# Events
# -------------------------
@bot.event
async def on_ready():
    print(f"Bot ist online als {bot.user}")

# -------------------------
# Basic test
# -------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

# -------------------------
# Moderation Commands
# -------------------------
@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Bitte 1-100 angeben.")
    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 wegen command message
    await ctx.send(f"🧹 Gelöscht: {len(deleted)-1} Nachrichten.", delete_after=5)
    await log_action(ctx.guild, f"🧹 CLEAR | {ctx.author} löschte {len(deleted)-1} msgs in #{ctx.channel}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason: str = "—"):
    if minutes < 1 or minutes > 10080:  # max 7 Tage
        return await ctx.send("❌ Minuten: 1 bis 10080 (7 Tage).")
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await ctx.send(f"⏱️ {member.mention} getimeoutet für **{minutes} min**. Grund: {reason}")
    await log_action(ctx.guild, f"⏱️ TIMEOUT | {ctx.author} -> {member} | {minutes} min | {reason}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "—"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} wurde gekickt. Grund: {reason}")
    await log_action(ctx.guild, f"👢 KICK | {ctx.author} -> {member} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "—"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member} wurde gebannt. Grund: {reason}")
    await log_action(ctx.guild, f"🔨 BAN | {ctx.author} -> {member} | {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user: str):
    # Accepts "Name#1234" or ID
    bans = [entry async for entry in ctx.guild.bans()]
    target = None

    if user.isdigit():
        uid = int(user)
        for entry in bans:
            if entry.user.id == uid:
                target = entry.user
                break
    else:
        for entry in bans:
            if str(entry.user) == user:
                target = entry.user
                break

    if not target:
        return await ctx.send("❌ User nicht im Ban-Log gefunden. Nutze Name#0000 oder ID.")
    await ctx.guild.unban(target)
    await ctx.send(f"✅ Unban: {target}")
    await log_action(ctx.guild, f"✅ UNBAN | {ctx.author} -> {target}")

# -------------------------
# Warn System (Datei-basiert)
# -------------------------
@bot.command()
async def warn(ctx, member: discord.Member, *, reason: str = "—"):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_warns()
    gid = str(ctx.guild.id)
    uid = str(member.id)
    data.setdefault(gid, {})
    data[gid].setdefault(uid, [])

    data[gid][uid].append({
        "mod": str(ctx.author),
        "reason": reason
    })

    save_warns(data)

    count = len(data[gid][uid])
    await ctx.send(f"⚠️ {member.mention} verwarnt. (**{count}** Warns) Grund: {reason}")
    await log_action(ctx.guild, f"⚠️ WARN | {ctx.author} -> {member} | #{count} | {reason}")

@bot.command()
async def warns(ctx, member: discord.Member):
    data = load_warns()
    gid = str(ctx.guild.id)
    uid = str(member.id)

    warns_list = data.get(gid, {}).get(uid, [])
    if not warns_list:
        return await ctx.send(f"✅ {member.mention} hat keine Warns.")

    lines = []
    for i, w in enumerate(warns_list[-10:], start=max(1, len(warns_list)-9)):
        lines.append(f"**{i}.** Mod: `{w['mod']}` | Grund: {w['reason']}")

    await ctx.send(f"⚠️ Warns für {member.mention} (**{len(warns_list)}**):\n" + "\n".join(lines))

@bot.command()
async def clearwarns(ctx, member: discord.Member):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_warns()
    gid = str(ctx.guild.id)
    uid = str(member.id)

    if gid in data and uid in data[gid]:
        del data[gid][uid]
        save_warns(data)
        await ctx.send(f"🧽 Warns gelöscht für {member.mention}.")
        await log_action(ctx.guild, f"🧽 CLEARWARNS | {ctx.author} -> {member}")
    else:
        await ctx.send("ℹ️ Keine Warns vorhanden.")

bot.run(TOKEN)