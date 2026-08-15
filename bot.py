"""
bot.py - Discord FAB Announcements Bot

Usage:
- Install dependencies: pip install -U discord.py
- Set the bot token in the DISCORD_TOKEN environment variable (never put tokens in code).
- Optionally set ANNOUNCE_CHANNEL_ID to a channel ID where announcements should be posted.
- Run: python bot.py

Commands:
- !announce <message>    Post an announcement (requires Manage Guild permission).
- !set_channel           Save the current channel as the announce channel (requires Manage Guild permission).
- !ping                  Basic liveness check.

This file intentionally does not store tokens in the repo. It can persist the announce channel in a local file announce_channel.txt.
"""

import os
import logging
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fab-bot")

# Config via environment
TOKEN = os.getenv("DISCORD_TOKEN")
ANNOUNCE_CHANNEL_ENV = os.getenv("ANNOUNCE_CHANNEL_ID")

PREFIX = "!"

intents = discord.Intents.default()
intents.message_content = True  # required for reading message content (bot needs intent enabled on dev portal)

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=commands.DefaultHelpCommand())

CHANNEL_FILE = "announce_channel.txt"


def load_saved_channel_id():
    # Priority: env var, then saved file
    if ANNOUNCE_CHANNEL_ENV:
        try:
            return int(ANNOUNCE_CHANNEL_ENV)
        except ValueError:
            logger.warning("ANNOUNCE_CHANNEL_ID env var is not an integer: %s", ANNOUNCE_CHANNEL_ENV)
    if os.path.exists(CHANNEL_FILE):
        try:
            with open(CHANNEL_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return int(content) if content else None
        except Exception as e:
            logger.exception("Failed to read %s: %s", CHANNEL_FILE, e)
    return None


def save_channel_id(channel_id: int):
    try:
        with open(CHANNEL_FILE, "w", encoding="utf-8") as f:
            f.write(str(channel_id))
        logger.info("Saved announce channel id %s to %s", channel_id, CHANNEL_FILE)
    except Exception:
        logger.exception("Failed to save announce channel id")


@bot.event
async def on_ready():
    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id)
    logger.info("Ready at %s", datetime.utcnow().isoformat())


@bot.command(name="ping")
async def ping(ctx):
    """Simple latency/check command."""
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! Latency: {latency_ms} ms")


@bot.command(name="set_channel")
@commands.has_permissions(manage_guild=True)
async def set_channel(ctx):
    """Save the current channel as the default announcement channel."""
    channel_id = ctx.channel.id
    save_channel_id(channel_id)
    await ctx.send(f"Canal de anúncios salvo: <#{channel_id}>")


@bot.command(name="announce")
@commands.has_permissions(manage_guild=True)
async def announce(ctx, *, message: str):
    """Post an announcement embed to the configured announce channel (or the current channel).

    Usage: !announce Mensagem aqui
    Requires the caller to have Manage Guild permission to avoid abuse.
    """
    channel_id = load_saved_channel_id()
    target = None
    if channel_id:
        target = bot.get_channel(channel_id)
        if target is None:
            logger.warning("Configured announce channel id %s not found", channel_id)

    if target is None:
        # fallback to the channel where the command was used
        target = ctx.channel

    embed = discord.Embed(
        title="📣 Anúncio FAB",
        description=message,
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text=f"Anúncio por {ctx.author}")

    try:
        await target.send(embed=embed)
        await ctx.send(f"Anúncio enviado em {target.mention}")
    except discord.Forbidden:
        await ctx.send("Não tenho permissão para enviar mensagens no canal de destino.")
    except Exception as e:
        logger.exception("Erro ao enviar anúncio: %s", e)
        await ctx.send("Falha ao enviar anúncio. Verifique os logs.")


@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Uso: !announce <mensagem>")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Você precisa da permissão 'Gerenciar Servidor' para usar este comando.")
    else:
        logger.exception("Erro no comando announce: %s", error)
        await ctx.send("Erro interno ao processar o comando.")


@set_channel.error
async def set_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Você precisa da permissão 'Gerenciar Servidor' para usar este comando.")
    else:
        logger.exception("Erro no comando set_channel: %s", error)
        await ctx.send("Erro interno ao processar o comando.")


if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN is not set. Exiting.")
        print("Error: set DISCORD_TOKEN environment variable before running the bot.")
        exit(1)

    try:
        bot.run(TOKEN)
    except Exception:
        logger.exception("Bot crashed")
