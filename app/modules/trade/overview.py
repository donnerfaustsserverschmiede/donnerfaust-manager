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

        # Recover previously posted overview messages if the saved message-ID table was
        # lost/reset, so a stock change edits the existing list instead of duplicating it.
        if not saved:
            recovered = {}
            async for old_message in channel.history(limit=100):
                if old_message.author.id == bot.user.id and old_message.content.startswith('📦 **Lagerübersicht · Seite '):
                    try:
                        page_text = old_message.content.split('Seite ', 1)[1].split('/', 1)[0]
                        recovered[int(page_text) - 1] = old_message.id
                    except (ValueError, IndexError):
                        continue
            if recovered:
                with _connect() as db:
                    for page, message_id in recovered.items():
                        db.execute(
                            'INSERT OR REPLACE INTO trade_overview_messages(guild_id,page,message_id) VALUES(?,?,?)',
                            (guild_id, page, message_id),
                        )
                saved = [{'page': page, 'message_id': message_id} for page, message_id in sorted(recovered.items())]
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


async def restore_items_from_overview(bot, guild_id: int) -> int:
    """Restore item names and stock from the persistent Discord overview if SQLite is empty."""
    with _connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS trade_items (
            guild_id INTEGER NOT NULL, item_id INTEGER NOT NULL, name TEXT NOT NULL COLLATE NOCASE,
            category TEXT NOT NULL DEFAULT 'Sonstiges', stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0),
            sell_price TEXT NOT NULL DEFAULT '0.00', buy_price TEXT NOT NULL DEFAULT '0.00',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(guild_id,item_id), UNIQUE(guild_id,name))''')
        existing = db.execute('SELECT COUNT(*) FROM trade_items WHERE guild_id=?', (guild_id,)).fetchone()[0]
    if existing:
        return 0

    channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    if not isinstance(channel, discord.TextChannel):
        return 0

    recovered = {}
    async for message in channel.history(limit=500):
        if message.author.id != bot.user.id or not message.content.startswith('📦 **Lagerübersicht · Seite '):
            continue
        for line in message.content.splitlines()[1:]:
            if ' — Bestand: ' not in line:
                continue
            name, raw_stock = line.rsplit(' — Bestand: ', 1)
            name = name.strip()
            try:
                stock = int(raw_stock.strip())
            except ValueError:
                continue
            if name and stock >= 0:
                recovered.setdefault(name.casefold(), (name, stock))

    if not recovered:
        log.warning('No old inventory items found in Discord overview for guild %s', guild_id)
        return 0

    with _connect() as db:
        next_id = db.execute('SELECT COALESCE(MAX(item_id),0)+1 FROM trade_items WHERE guild_id=?', (guild_id,)).fetchone()[0]
        restored = 0
        for name, stock in recovered.values():
            db.execute('''INSERT OR IGNORE INTO trade_items
                (guild_id,item_id,name,category,stock,sell_price,buy_price)
                VALUES(?,?,?,'Sonstiges',?,'0.00','0.00')''',
                (guild_id, next_id, name, stock))
            if db.execute('SELECT changes()').fetchone()[0]:
                restored += 1
                next_id += 1
    log.warning('Restored %s inventory items from Discord overview for guild %s', restored, guild_id)
    return restored
