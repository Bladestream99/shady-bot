import os
import json
from datetime import timedelta, datetime

import discord
from discord.ext import commands
from discord.ui import View

TOKEN = os.getenv("TOKEN")

# ====== IDs eintragen ======
LOG_CHANNEL_ID = 0           # z.B. 123456789012345678
STAFF_ROLE_ID = 0            # z.B. 123456789012345678
TICKET_CATEGORY_ID = 0       # z.B. 123456789012345678, oder 0 lassen
DATA_FILE = "moddata.json"

# ====== Intents ======
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# Helpers
# =========================
def now_string() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


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
        "bans": [],
        "timeouts": [],
        "kicks": []
    })
    return data[gid][uid]


def is_mod(ctx: commands.Context) -> bool:
    perms = ctx.author.guild_permissions
    return (
        perms.administrator
        or perms.moderate_members
        or perms.kick_members
        or perms.ban_members
        or perms.manage_messages
    )


async def log_action(guild: discord.Guild, text: str):
    if LOG_CHANNEL_ID == 0:
        return
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(text)


async def fetch_user_display(bot_instance: commands.Bot, user_id: int) -> str:
    try:
        user = bot_instance.get_user(user_id) or await bot_instance.fetch_user(user_id)
        return f"{user} ({user_id})"
    except Exception:
        return f"Unbekannter User ({user_id})"


# =========================
# Ticket Views
# =========================
class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ticket schließen",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket_button"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.channel:
            return await interaction.response.send_message("❌ Kanal nicht gefunden.", ephemeral=True)

        await interaction.response.send_message("🔒 Ticket wird geschlossen...", ephemeral=True)

        try:
            await log_action(interaction.guild, f"🔒 TICKET CLOSED | {interaction.user} | #{interaction.channel.name}")
        except Exception:
            pass

        await interaction.channel.delete()


class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ticket erstellen",
        style=discord.ButtonStyle.success,
        emoji="🎫",
        custom_id="create_ticket_button"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        if guild is None:
            return await interaction.response.send_message("❌ Das geht nur auf einem Server.", ephemeral=True)

        # Prüfen, ob bereits ein Ticket existiert
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.id}")
        if existing:
            return await interaction.response.send_message(
                f"❌ Du hast bereits ein Ticket: {existing.mention}",
                ephemeral=True
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True
            )
        }

        if STAFF_ROLE_ID != 0:
            staff_role = guild.get_role(STAFF_ROLE_ID)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID != 0 else None

        channel = await guild.create_text_channel(
            name=f"ticket-{user.id}",
            overwrites=overwrites,
            category=category
        )

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Hallo {user.mention}, willkommen in deinem Ticket.\n\n"
                f"Beschreibe bitte dein Anliegen möglichst genau.\n"
                f"Ein Teammitglied wird dir helfen."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"User-ID: {user.id}")

        await channel.send(content=user.mention, embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)
        await log_action(guild, f"🎫 TICKET OPEN | {user} | {channel.mention}")


# =========================
# Events
# =========================
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(CloseTicketView())
    print(f"Bot ist online als {bot.user}")


# =========================
# Basic
# =========================
@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")


# =========================
# Moderation
# =========================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Bitte eine Zahl von 1 bis 100 angeben.")

    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 {len(deleted) - 1} Nachrichten gelöscht.", delete_after=5)
    await log_action(ctx.guild, f"🧹 CLEAR | {ctx.author} | {len(deleted)-1} Nachrichten in #{ctx.channel}")


@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason: str = "—"):
    if minutes < 1 or minutes > 10080:
        return await ctx.send("❌ Minuten müssen zwischen 1 und 10080 liegen.")

    await member.timeout(timedelta(minutes=minutes), reason=reason)

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, member.id)
    entry["timeouts"].append({
        "mod": str(ctx.author),
        "reason": reason,
        "minutes": minutes,
        "time": now_string()
    })
    save_data(data)

    await ctx.send(f"⏱️ {member.mention} wurde für **{minutes} Minuten** getimeoutet. Grund: {reason}")
    await log_action(ctx.guild, f"⏱️ TIMEOUT | {ctx.author} -> {member} ({member.id}) | {minutes}m | {reason}")


@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "—"):
    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, member.id)
    entry["kicks"].append({
        "mod": str(ctx.author),
        "reason": reason,
        "time": now_string()
    })
    save_data(data)

    await member.kick(reason=reason)
    await ctx.send(f"👢 {member} wurde gekickt. Grund: {reason}")
    await log_action(ctx.guild, f"👢 KICK | {ctx.author} -> {member} ({member.id}) | {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def banid(ctx, user_id: int, *, reason: str = "—"):
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        await ctx.guild.ban(user, reason=reason)
    except Exception as e:
        return await ctx.send(f"❌ Ban fehlgeschlagen: {e}")

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, user_id)
    entry["bans"].append({
        "mod": str(ctx.author),
        "reason": reason,
        "time": now_string()
    })
    save_data(data)

    await ctx.send(f"🔨 User-ID `{user_id}` wurde gebannt.")
    await log_action(ctx.guild, f"🔨 BAN | {ctx.author} -> {user_id} | {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
    except Exception as e:
        return await ctx.send(f"❌ Unban fehlgeschlagen: {e}")

    await ctx.send(f"✅ User-ID `{user_id}` wurde entbannt.")
    await log_action(ctx.guild, f"✅ UNBAN | {ctx.author} -> {user_id}")


# =========================
# Notes / Warns / Userlog
# =========================
@bot.command()
async def note(ctx, user_id: int, *, text: str):
    if not is_mod(ctx):
        return await ctx.send("❌ Keine Rechte.")

    data = load_data()
    entry = ensure_user_entry(data, ctx.guild.id, user_id)
    entry["notes"].append({
        "mod": str(ctx.author),
        "text": text,
        "time": now_string()
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
        "reason": reason,
        "time": now_string()
    })
    save_data(data)

    await ctx.send(f"⚠️ Warnung für User-ID `{user_id}` gespeichert.")
    await log_action(ctx.guild, f"⚠️ WARN | {ctx.author} -> {user_id} | {reason}")


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

    user_display = await fetch_user_display(bot, user_id)

    notes = entry.get("notes", [])
    warns = entry.get("warns", [])
    bans = entry.get("bans", [])
    timeouts = entry.get("timeouts", [])
    kicks = entry.get("kicks", [])

    embed = discord.Embed(
        title="📁 User-Akte",
        description=f"**User:** {user_display}",
        color=discord.Color.blurple()
    )

    def format_items(items, key_text, extra_key=None):
        if not items:
            return "Keine"
        lines = []
        for item in items[-5:]:
            extra = f" | {item.get(extra_key)}" if extra_key and item.get(extra_key) is not None else ""
            lines.append(
                f"• {item.get('time', '—')} | {item.get('mod', '—')} | {item.get(key_text, '—')}{extra}"
            )
        return "\n".join(lines)

    embed.add_field(name=f"📝 Notes ({len(notes)})", value=format_items(notes, "text"), inline=False)
    embed.add_field(name=f"⚠️ Warns ({len(warns)})", value=format_items(warns, "reason"), inline=False)
    embed.add_field(name=f"🔨 Bans ({len(bans)})", value=format_items(bans, "reason"), inline=False)
    embed.add_field(name=f"⏱️ Timeouts ({len(timeouts)})", value=format_items(timeouts, "reason", "minutes"), inline=False)
    embed.add_field(name=f"👢 Kicks ({len(kicks)})", value=format_items(kicks, "reason"), inline=False)

    await ctx.send(embed=embed)


# =========================
# Ticket Panel Command
# =========================
@bot.command()
@commands.has_permissions(administrator=True)
async def panel(ctx):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Klicke auf den Button unten, um ein Ticket zu erstellen.",
        color=discord.Color.blurple()
    )
    await ctx.send(embed=embed, view=TicketPanelView())


# =========================
# Error Handler
# =========================
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Argument fehlt.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Du hast dafür keine Rechte.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Falsches Argument.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send(f"❌ Fehler: {error}")


bot.run(TOKEN)
