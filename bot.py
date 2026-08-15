"""
bot.py - Discord FAB Official Announcements Bot (slash commands)

- Uses slash (/ ) commands and app commands registration.
- Reads the bot token from the DISCORD_TOKEN environment variable only.
- Persists announcement channel per-guild in announce_channels.json.
- Commands added: /anuncio, /comunicado, /avaliacao, /booster, /worldcup, /regras, /ajuda
- Administrative commands require Administrator permission.
"""

from __future__ import annotations
import os
import json
import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fab-bot")

# Environment config
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNELS_FILE = "announce_channels.json"

# FAB identity color and footer
FAB_COLOR = discord.Color.from_rgb(0, 102, 204)  # azul FAB
FAB_FOOTER = "FAB • Federación Argentina de Beatball 🇦🇷"

intents = discord.Intents.default()
# message_content intent not required for slash commands, keep minimal

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Persistence (per-guild announce channel) ---

def load_channels() -> dict:
    if not os.path.exists(CHANNELS_FILE):
        return {}
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load %s", CHANNELS_FILE)
        return {}


def save_channels(channels: dict) -> None:
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=2)
    except Exception:
        logger.exception("Failed to save %s", CHANNELS_FILE)


def get_saved_channel_for_guild(guild_id: int) -> Optional[int]:
    channels = load_channels()
    return channels.get(str(guild_id))


def set_saved_channel_for_guild(guild_id: int, channel_id: int) -> None:
    channels = load_channels()
    channels[str(guild_id)] = channel_id
    save_channels(channels)


# --- Helpers ---

def make_fab_embed(title: Optional[str], description: str, author: Optional[str] = None, image_url: Optional[str] = None) -> discord.Embed:
    title_text = title if title else "📣 Anuncio FAB"
    embed = discord.Embed(
        title=title_text,
        description=description,
        color=FAB_COLOR,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=FAB_FOOTER)
    if author:
        embed.set_author(name=author)
    if image_url:
        embed.set_image(url=image_url)
    return embed


async def send_announcement_to_channel(channel: discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.TextChannel, embed: discord.Embed) -> bool:
    try:
        await channel.send(embed=embed)
        return True
    except discord.Forbidden:
        logger.warning("Missing permission to send in channel %s", channel)
        return False
    except Exception:
        logger.exception("Failed sending announcement to %s", channel)
        return False


# --- Command checks ---

def is_guild_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    member = interaction.user
    # member may be of type discord.Member in guild context
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator


def admin_check(interaction: discord.Interaction) -> bool:
    if not is_guild_admin(interaction):
        raise app_commands.AppCommandError("Você precisa da permissão de Administrador para usar este comando.")
    return True


# --- Slash commands ---

@bot.event
async def on_ready():
    # Sync global commands (may take up to an hour to appear globally).
    # For faster registration during development, consider guild-specific sync.
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d commands", len(synced))
    except Exception:
        logger.exception("Failed to sync commands")

    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id)


# /ajuda - public help
@bot.tree.command(name="ajuda", description="Mostrar ajuda dos comandos FAB")
async def ajuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Ajuda — FAB Announcements Bot",
        color=FAB_COLOR,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="/anuncio [titulo] mensagem [imagem?] [canal?]", value="Enviar anúncio oficial da FAB.", inline=False)
    embed.add_field(name="/comunicado mensagem [imagem?] [canal?]", value="Comunicados oficiais.", inline=False)
    embed.add_field(name="/avaliacao mensagem [imagem?] [canal?]", value="Avaliações e resultados.", inline=False)
    embed.add_field(name="/booster mensagem [imagem?] [canal?]", value="Promoções e booster.", inline=False)
    embed.add_field(name="/worldcup mensagem [imagem?] [canal?]", value="Conteúdo relacionado à World Cup.", inline=False)
    embed.add_field(name="/regras mensagem [imagem?] [canal?]", value="Publicar regras e atualizações de regras.", inline=False)
    embed.add_field(name="Permissões", value="Comandos administrativos exigem permissão de Administrador.", inline=False)
    embed.set_footer(text=FAB_FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Template for admin announcement commands
async def _announce_interaction(interaction: discord.Interaction, default_title: Optional[str], message: str, image: Optional[discord.Attachment], channel: Optional[discord.TextChannel]):
    # Admin check
    if not is_guild_admin(interaction):
        await interaction.response.send_message("Você precisa da permissão de Administrador para usar este comando.", ephemeral=True)
        return

    # Determine target channel: explicit channel -> saved channel -> current channel
    target_channel = None
    if channel is not None:
        target_channel = channel
    else:
        saved_id = get_saved_channel_for_guild(interaction.guild.id) if interaction.guild else None
        if saved_id:
            target_channel = interaction.guild.get_channel(int(saved_id)) if interaction.guild else None

    if target_channel is None:
        # fallback to channel where command was used
        target_channel = interaction.channel

    image_url = None
    if image is not None:
        # Attachments passed to slash commands are accessible via url
        image_url = image.url

    author_text = f"{interaction.user.display_name}"
    embed = make_fab_embed(default_title, message, author=author_text, image_url=image_url)

    await interaction.response.defer(ephemeral=False)
    success = await send_announcement_to_channel(target_channel, embed)
    if success:
        await interaction.followup.send(f"Anúncio enviado em {target_channel.mention}")
    else:
        await interaction.followup.send("Falha ao enviar o anúncio. Verifique permissões e logs.")


# Register admin commands
@bot.tree.command(name="anuncio", description="Enviar anúncio oficial da FAB")
@app_commands.describe(titulo="Título opcional do anúncio", mensagem="Conteúdo do anúncio", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def anuncio(interaction: discord.Interaction, mensagem: str, titulo: Optional[str] = None, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, titulo or "📣 Anuncio FAB", mensagem, imagem, canal)


@bot.tree.command(name="comunicado", description="Enviar comunicado oficial da FAB")
@app_commands.describe(mensagem="Conteúdo do comunicado", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def comunicado(interaction: discord.Interaction, mensagem: str, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, "📢 Comunicado FAB", mensagem, imagem, canal)


@bot.tree.command(name="avaliacao", description="Publicar avaliação / resultado")
@app_commands.describe(mensagem="Conteúdo da avaliação", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def avaliacao(interaction: discord.Interaction, mensagem: str, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, "📝 Avaliação FAB", mensagem, imagem, canal)


@bot.tree.command(name="booster", description="Anúncio de booster / promoção")
@app_commands.describe(mensagem="Conteúdo do booster", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def booster(interaction: discord.Interaction, mensagem: str, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, "🚀 Booster FAB", mensagem, imagem, canal)


@bot.tree.command(name="worldcup", description="Anúncios relacionados à World Cup")
@app_commands.describe(mensagem="Conteúdo da worldcup", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def worldcup(interaction: discord.Interaction, mensagem: str, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, "🏆 World Cup — FAB", mensagem, imagem, canal)


@bot.tree.command(name="regras", description="Publicar regras ou atualizações de regras")
@app_commands.describe(mensagem="Conteúdo das regras", imagem="Imagem (opcional)", canal="Canal de destino (opcional)")
async def regras(interaction: discord.Interaction, mensagem: str, imagem: Optional[discord.Attachment] = None, canal: Optional[discord.TextChannel] = None):
    await _announce_interaction(interaction, "📜 Regras — FAB", mensagem, imagem, canal)


# Admin-only helper to set guild default announce channel
@bot.tree.command(name="set_canal_anuncios", description="Salvar o canal atual como canal padrão de anúncios (Administrador)")
@app_commands.checks.has_permissions(administrator=True)
async def set_canal_anuncios(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("Esse comando só pode ser usado em servidores (guilds).", ephemeral=True)
        return
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Use esse comando em um canal de texto.", ephemeral=True)
        return
    set_saved_channel_for_guild(interaction.guild.id, channel.id)
    await interaction.response.send_message(f"Canal de anúncios salvo: {channel.mention}")


# Error handlers
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Generic handler for app command errors
    logger.exception("App command error: %s", error)
    try:
        await interaction.response.send_message(str(error), ephemeral=True)
    except Exception:
        # appeared after response, try followup
        try:
            await interaction.followup.send(str(error), ephemeral=True)
        except Exception:
            logger.exception("Failed to send error message")


# Run
if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN is not set. Exiting.")
        print("Error: set DISCORD_TOKEN environment variable before running the bot.")
        raise SystemExit(1)

    try:
        bot.run(TOKEN)
    except Exception:
        logger.exception("Bot crashed")
