import logging
import sqlite3
import discord
from app.core.database import DB_PATH

log = logging.getLogger(__name__)
CHANNEL_ID = 1564254631658393701

def _connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    return db

async def refresh(bot, guild_id: int):
    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        with _connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS trade_overview_messages (guild_id INTEGER NOT NULL, page INTEGER NOT NULL, message_id INTEGER NOT NULL, PRIMARY KEY(guild_id,page))')
            rows = db.execute('SELECT name, stock FROM trade_items WHERE guild_id=? ORDER BY name COLLATE NOCASE', (guild_id,)).fetchall()
            saved = db.execute('SELECT page, message_id FROM trade_overview_messages WHERE guild_id=? ORDER BY page', (guild_id,)).fetchall()
        lines = [str(row['name']) + ' — Bestand: ' + str(row['stock']) for row in rows]
        chunks, current = [], []
        for line in lines:
            if current and len('\n'.join(current + [line])) > 1750:
                chunks.append(current)
                current = []
            current.append(line)
        if current or not chunks:
            chunks.append(current)
        known = {row['page']: row['message_id'] for row in saved}
        for page, chunk in enumerate(chunks):
            body = '📦 **Lagerübersicht · Seite ' + str(page + 1) + '/' + str(len(chunks)) + '**\n' + ('\n'.join(chunk) if chunk else 'Noch keine Artikel.')
            message = None
            if page in known:
                try:
                    message = await channel.fetch_message(known[page])
                    await message.edit(content=body)
                except discord.NotFound:
                    message = None
            if message is None:
                message = await channel.send(body)
                with _connect() as db:
                    db.execute('INSERT OR REPLACE INTO trade_overview_messages(guild_id,page,message_id) VALUES(?,?,?)', (guild_id, page, message.id))
        for page, message_id in known.items():
            if page >= len(chunks):
                try:
                    old = await channel.fetch_message(message_id)
                    await old.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                with _connect() as db:
                    db.execute('DELETE FROM trade_overview_messages WHERE guild_id=? AND page=?', (guild_id, page))
    except (discord.Forbidden, discord.HTTPException, sqlite3.Error):
        log.exception('Could not refresh inventory overview')
