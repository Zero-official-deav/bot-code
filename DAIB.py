import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import threading
import discord
import requests
import asyncio
from collections import deque
import random
import os
import time
import json

# =========================
# GLOBALS & STORAGE
# =========================

bot = None
bot_thread = None
running = False

user_limits = {}
DEFAULT_LIMIT = 17

activated_users = {}
regeneration_trackers = set()

DISCORD_TOKEN = ""
OPENROUTER_API_KEY = ""

AUTHORIZED_USERS = {1507727597428146317}
TARGET_CHANNEL_ID = 1517569331255312607

BOT_MODE = "normal"
STEALTH_MODE = False
FORCED_MESSAGE = None
LAST_CHANNEL = None
LAST_USER_VOICE_STATE = None

SOUNDS_DIR = "sounds"
channel_active_users = {}

active_trades = {}
pending_takes = {}
pending_gives = {}

# Role Shop System
ROLE_SHOP_FILE = "role_shop.json"
role_shop = {}
user_inventory = {}

# Tradeable Roles (separate from shop)
TRADEABLE_ROLES_FILE = "tradeable_roles.json"
tradeable_roles = {}  # { "001": { "role_id": 123456789, "role_name": "...", "tradeable": True }, ... }

# Sellable Roles
SELLABLE_ROLES_FILE = "sellable_roles.json"
sellable_roles = {}  # { "001": { "role_id": 123456789, "role_name": "...", "sell_price": 100 }, ... }

TRADE_STATUS_FILE = "trade_status.json"
user_trade_settings = {}

ECONOMY_FILE = "economy.json"
user_wallets = {}
user_permissions = {}

# Bot Personality
BOT_PERSONALITY = "You are XBot. No AI assistant behavior. No roleplay actions."
PERSONALITY_FILE = "personality.json"

# Channel IDs for specific features
ABILITIES_SHOP_CHANNEL_ID = 1517627115208441916  # !purchase channel
ROLES_SHOP_CHANNEL_ID = 1517627756907593738     # !buy channel
TRADE_CHANNEL_ID = 1517627548173861074          # !trade channel

# Load all persistent data
def load_all_data():
    global role_shop, user_inventory, user_trade_settings, user_wallets, user_permissions, user_limits, tradeable_roles, sellable_roles, BOT_PERSONALITY
    
    if os.path.exists(ROLE_SHOP_FILE):
        try:
            with open(ROLE_SHOP_FILE, "r") as f:
                role_shop = json.load(f)
        except Exception as e:
            print("Failed to load role shop:", e)
    
    if os.path.exists(TRADEABLE_ROLES_FILE):
        try:
            with open(TRADEABLE_ROLES_FILE, "r") as f:
                tradeable_roles = json.load(f)
        except Exception as e:
            print("Failed to load tradeable roles:", e)
    
    if os.path.exists(SELLABLE_ROLES_FILE):
        try:
            with open(SELLABLE_ROLES_FILE, "r") as f:
                sellable_roles = json.load(f)
        except Exception as e:
            print("Failed to load sellable roles:", e)
    
    if os.path.exists("user_inventory.json"):
        try:
            with open("user_inventory.json", "r") as f:
                data = json.load(f)
                user_inventory = {int(k): v for k, v in data.items()}
        except Exception as e:
            print("Failed to load user inventory:", e)
    
    if os.path.exists(TRADE_STATUS_FILE):
        try:
            with open(TRADE_STATUS_FILE, "r") as f:
                data = json.load(f)
                user_trade_settings = {int(k): v for k, v in data.items()}
        except Exception as e:
            print("Failed to load trade settings:", e)
    
    if os.path.exists(ECONOMY_FILE):
        try:
            with open(ECONOMY_FILE, "r") as f:
                data = json.load(f)
                user_wallets = {int(k): v for k, v in data.get("wallets", {}).items()}
                user_permissions = {int(k): v for k, v in data.get("permissions", {}).items()}
                user_limits = {int(k): v for k, v in data.get("limits", {}).items()}
        except Exception as e:
            print("Failed to load economy:", e)
    
    if os.path.exists(PERSONALITY_FILE):
        try:
            with open(PERSONALITY_FILE, "r") as f:
                data = json.load(f)
                BOT_PERSONALITY = data.get("personality", BOT_PERSONALITY)
        except Exception as e:
            print("Failed to load personality:", e)

load_all_data()

def save_role_shop():
    try:
        with open(ROLE_SHOP_FILE, "w") as f:
            json.dump(role_shop, f, indent=2)
    except Exception as e:
        print("Failed to save role shop:", e)

def save_tradeable_roles():
    try:
        with open(TRADEABLE_ROLES_FILE, "w") as f:
            json.dump(tradeable_roles, f, indent=2)
    except Exception as e:
        print("Failed to save tradeable roles:", e)

def save_sellable_roles():
    try:
        with open(SELLABLE_ROLES_FILE, "w") as f:
            json.dump(sellable_roles, f, indent=2)
    except Exception as e:
        print("Failed to save sellable roles:", e)

def save_user_inventory():
    try:
        with open("user_inventory.json", "w") as f:
            json.dump({str(k): v for k, v in user_inventory.items()}, f, indent=2)
    except Exception as e:
        print("Failed to save user inventory:", e)

def save_trade_settings():
    try:
        with open(TRADE_STATUS_FILE, "w") as f:
            json.dump({str(k): v for k, v in user_trade_settings.items()}, f, indent=2)
    except Exception as e:
        print("Failed to save trade settings:", e)

def save_economy():
    try:
        with open(ECONOMY_FILE, "w") as f:
            json.dump({
                "wallets": {str(k): v for k, v in user_wallets.items()},
                "permissions": {str(k): v for k, v in user_permissions.items()},
                "limits": {str(k): v for k, v in user_limits.items()}
            }, f)
    except Exception as e:
        print("Failed to save economy:", e)

def save_personality():
    try:
        with open(PERSONALITY_FILE, "w") as f:
            json.dump({"personality": BOT_PERSONALITY}, f)
    except Exception as e:
        print("Failed to save personality:", e)

def get_coins(uid):
    if uid not in user_wallets:
        user_wallets[uid] = 0
        save_economy()
    return user_wallets[uid]

def add_coins(uid, amount):
    user_wallets[uid] = max(0, get_coins(uid) + amount)
    save_economy()

def check_permission(uid, perm_node):
    if uid in AUTHORIZED_USERS:
        return True
    if uid not in user_permissions:
        return False
    return user_permissions[uid].get(perm_node, False)

def grant_permission(uid, perm_node, value=True):
    if uid not in user_permissions:
        user_permissions[uid] = {}
    user_permissions[uid][perm_node] = value
    save_economy()

# =========================
# MEMORY SYSTEM
# =========================

memory = {}

def get_memory(channel_id):
    if channel_id not in memory:
        memory[channel_id] = deque(maxlen=30)
    return memory[channel_id]

def format_memory(channel_id):
    return "\n".join(get_memory(channel_id))

# =========================
# PERSONALITY SYSTEM
# =========================

def get_personality():
    return BOT_PERSONALITY

# =========================
# AI FUNCTION (TEXT ONLY)
# =========================

def ask_ai(api_key, prompt, is_authorized, channel_id, uid=None, autonomous=False):
    global BOT_MODE

    # Check if API key is set
    if not api_key or api_key.strip() == "":
        print("ERROR: OPENROUTER_API_KEY is not set!")
        return "AI error 💀"

    mode_text = {
        "normal": "NORMAL MODE",
        "chill": "CHILL MODE: calm",
        "aggressive": "AGGRESSIVE MODE: dominant"
    }[BOT_MODE]

    history = format_memory(channel_id)
    personality = get_personality()

    friendship_status = ""
    if uid and check_permission(uid, "friendship"):
        friendship_status = "\nNOTIFICATION: The current user interacting with you bought 'Friendship' from your shop. Treat them like an absolute close friend, homie, or VIP."

    system_behavior = (
        f"{mode_text}\n"
        f"{personality}\n\n"
        "You are Bart.\n"
        "You remember recent conversation history.\n"
        "You can see usernames, displaynames, mentions, replies, channel names.\n"
        f"Talk casually like a genuine Discord user. Use slang, lowercase, or typos if it fits your vibe.{friendship_status}\n"
        "CRITICAL: You are allowed and encouraged to tag/mention users using <@user_id> if you want to get their attention, call them out, or reply directly to them.\n"
    )

    if autonomous:
        system_behavior += "CONTEXT: You are sending this message completely unprompted out of nowhere because you felt like talking."
    else:
        system_behavior += "Talk casually like a Discord user."

    user_content = f"CHAT HISTORY:\n{history}\n\nUSER PROMPT / CONTEXT:\n{prompt}"

    try:
        print(f"[DEBUG] Sending AI request with API key: {api_key[:10]}...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "XBot"
            },
            json={
                "model": "google/gemini-2.5-flash", 
                "max_tokens": 100,  
                "messages": [
                    {
                        "role": "system",
                        "content": system_behavior
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            },
            timeout=30
        )

        print(f"[DEBUG] Response status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[ERROR] API returned non-200 status: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return "AI error 💀"

        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"[ERROR] No choices in response: {data}")
            return "AI error 💀"

        message_content = data["choices"][0]["message"]["content"]
        if not message_content or message_content.strip() == "":
            print(f"[ERROR] Empty message content in response")
            return "AI error 💀"

        print(f"[DEBUG] AI response received: {message_content[:50]}...")
        return message_content

    except requests.exceptions.Timeout:
        print("[ERROR] API request timed out (30 seconds)")
        return "AI error 💀"
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection error: {e}")
        return "AI error 💀"
    except ValueError as e:
        print(f"[ERROR] JSON parsing error: {e}")
        return "AI error 💀"
    except Exception as e:
        print(f"[ERROR] Unexpected error in ask_ai: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return "AI error 💀"

# =========================
# DISCORD BOT
# =========================

def start_bot():
    global bot, STEALTH_MODE, FORCED_MESSAGE, LAST_CHANNEL

    if not os.path.exists(SOUNDS_DIR):
        os.makedirs(SOUNDS_DIR)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.voice_states = True 

    bot = discord.Client(intents=intents)

    async def regenerate_user_limit(uid):
        global user_limits, regeneration_trackers
        await asyncio.sleep(900)  
        user_limits[uid] = user_limits.get(uid, 0) + 17
        save_economy()
        regeneration_trackers.remove(uid)

    async def autonomous_chatter_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(random.randint(1200, 2700))
            
            target_channel = bot.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                try:
                    recent_users = channel_active_users.get(target_channel.id, [])
                    if recent_users:
                        target_user = random.choice(recent_users)
                        auto_prompt = f"Say something out of nowhere. You can mention <@{target_user['id']}>."
                    else:
                        auto_prompt = "Say something completely out of nowhere to the chat."

                    async with target_channel.typing():
                        reply = ask_ai(OPENROUTER_API_KEY, auto_prompt, True, target_channel.id, autonomous=True)
                    
                    if reply and reply != "AI error 💀":
                        get_memory(target_channel.id).append(f"Bart (Autonomous): {reply}")
                        await target_channel.send(reply)
                except Exception as e:
                    print("Autonomous chatter failed:", e)

    async def join_and_play_audio(target_vc):
        try:
            vc_client = await target_vc.connect()
            start_time = time.time()
            while time.time() - start_time < 60 and vc_client.is_connected():
                sound_files = [f for f in os.listdir(SOUNDS_DIR) if f.endswith(('.mp3', '.wav'))]
                if sound_files:
                    sound_path = os.path.join(SOUNDS_DIR, random.choice(sound_files))
                    vc_client.play(discord.FFmpegPCMAudio(sound_path))
                    elapsed = 0
                    while vc_client.is_playing() and elapsed < 40:
                        await asyncio.sleep(1)
                        elapsed += 1
                else:
                    await asyncio.sleep(10)
                    break
                await asyncio.sleep(random.randint(10, 20))
            await vc_client.disconnect()
        except:
            if bot.voice_clients:
                for vc in bot.voice_clients:
                    try: await vc.disconnect()
                    except: pass

    async def voice_cycle_loop():
        await bot.wait_until_ready()
        while not bot.is_closed():
            await asyncio.sleep(300)
            target_vc = None
            if LAST_USER_VOICE_STATE and LAST_USER_VOICE_STATE.channel:
                target_vc = LAST_USER_VOICE_STATE.channel
            if not target_vc:
                for guild in bot.guilds:
                    for vc in guild.voice_channels:
                        if len(vc.members) > 0:
                            target_vc = vc
                            break
                    if target_vc: break
            if target_vc:
                await join_and_play_audio(target_vc)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")
        bot.loop.create_task(autonomous_chatter_loop())
        bot.loop.create_task(voice_cycle_loop())

    @bot.event
    async def on_message(message):
        global LAST_CHANNEL, activated_users, user_limits, regeneration_trackers, channel_active_users, LAST_USER_VOICE_STATE
        global active_trades, pending_takes, pending_gives

        if message.author.bot:
            return

        content = message.content.strip()
        uid = message.author.id
        content_lower = content.lower()

        if content in ["", ".", "..."]:
            return

        # ===================================================
        # DM TRADE RESPONSE (Handle before channel check)
        # ===================================================
        if isinstance(message.channel, discord.DMChannel):
            if content_lower in ["!agree", "!decline"]:
                target_id = message.author.id

                if target_id in active_trades:
                    trade_data = active_trades[target_id]
                    guild = bot.get_guild(trade_data["guild_id"])
                    origin_channel = bot.get_channel(trade_data["channel_id"])
                    
                    if not guild:
                        await message.reply("❌ Error: Server not found.")
                        return

                    initiator = guild.get_member(trade_data["initiator_id"])
                    target_member = guild.get_member(target_id)

                    if content_lower == "!decline":
                        await message.reply("🛑 You declined the trade.")
                        if initiator:
                            try:
                                await initiator.send(f"❌ **{target_member.display_name}** declined your trade.")
                            except: pass
                        if origin_channel:
                            await origin_channel.send(f"❌ <@{target_member.id}> declined the trade.")
                        del active_trades[target_id]
                        return

                    if not initiator or not target_member:
                        await message.reply("❌ Error: Trade data invalid.")
                        del active_trades[target_id]
                        return

                    try:
                        # Execute role swaps for ALL roles being traded
                        take_role_ids = trade_data.get("take_role_ids", [])
                        give_role_ids = trade_data.get("give_role_ids", [])
                        
                        # Remove taken roles from target, add to initiator
                        for role_id in take_role_ids:
                            role = guild.get_role(role_id)
                            if role:
                                await target_member.remove_roles(role, reason="Trade executed.")
                                await initiator.add_roles(role, reason="Trade executed.")
                        
                        # Remove given roles from initiator, add to target
                        for role_id in give_role_ids:
                            role = guild.get_role(role_id)
                            if role:
                                await initiator.remove_roles(role, reason="Trade executed.")
                                await target_member.add_roles(role, reason="Trade executed.")

                        # Handle coin transfer
                        coin_amount = trade_data.get("coin_amount", 0)
                        if coin_amount > 0:
                            coin_direction = trade_data.get("coin_direction", "to_target")
                            if coin_direction == "to_target":
                                add_coins(target_id, coin_amount)
                                add_coins(trade_data["initiator_id"], -coin_amount)
                            else:
                                add_coins(trade_data["initiator_id"], coin_amount)
                                add_coins(target_id, -coin_amount)

                        take_role_names = trade_data.get("take_role_names", [])
                        give_role_names = trade_data.get("give_role_names", [])
                        
                        confirmation_msg = f"✅ Trade complete!"
                        if take_role_names:
                            confirmation_msg += f" You got **{', '.join(take_role_names)}**"
                        if coin_amount > 0:
                            if coin_direction == "to_target":
                                confirmation_msg += f" and **{coin_amount} Coins**"
                            confirmation_msg += "!"
                        else:
                            confirmation_msg += "!"
                        
                        await message.reply(confirmation_msg)
                        
                        try:
                            initiator_msg = f"🎉 Trade approved!"
                            if give_role_names:
                                initiator_msg += f" You got **{', '.join(give_role_names)}**"
                            if coin_amount > 0 and coin_direction == "to_initiator":
                                initiator_msg += f" and **{coin_amount} Coins**"
                            initiator_msg += "!"
                            await initiator.send(initiator_msg)
                        except: pass
                        
                        if origin_channel:
                            await origin_channel.send(f"🤝 **Trade Complete!** <@{initiator.id}> and <@{target_member.id}> swapped roles and items!")
                    
                    except discord.Forbidden:
                        await message.reply("❌ Permission Error: I can't modify roles.")
                        if origin_channel:
                            await origin_channel.send(f"❌ Trade failed: Permission issue.")
                    
                    del active_trades[target_id]
                else:
                    await message.reply("❌ No active trades.")
            return

        # ===================================================
        # SETTINGS COMMAND (works in any channel)
        # ===================================================
        if content_lower == "!settings":
            settings_msg = (
                "⚙️ **YOUR SETTINGS** ⚙️\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📦 **INVENTORY VISIBILITY:**\n"
                "`!set inventory public` - Show all roles with codes\n"
                "`!set inventory anonymous` - Hide role codes\n"
                "`!set inventory hidden` - Hide inventory completely\n\n"
                "🔄 **TRADING SETTINGS:**\n"
                "`!set trading allowed` - Everyone can trade with you\n"
                "`!set trading disabled` - No one can trade with you\n"
                "`!set trading friends` - Friends only\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await message.author.send(settings_msg)
                await message.reply("✅ Settings sent to your DMs!")
            except:
                await message.reply("❌ I can't send you DMs. Check your privacy settings.")
            return

        # ===================================================
        # ABILITIES SHOP SYSTEM - Only in designated channel
        # ===================================================

        if content_lower == "!shop":
            if message.channel.id != ABILITIES_SHOP_CHANNEL_ID:
                await message.reply(f"❌ The abilities shop can only be accessed in <#{ABILITIES_SHOP_CHANNEL_ID}>")
                return
            
            await message.reply(
                "🛒 **BART'S MARKETPLACE** 🛒\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔹 `!purchase limit` | **Cost: 50 Coins**\n"
                "   ↳ Extends your chat limit by +15 messages.\n\n"
                "🔹 `!purchase vc` | **Cost: 100 Coins**\n"
                "   ↳ Unlock the ability to command: `bart join the vc`.\n\n"
                "🔹 `!purchase stealth` | **Cost: 250 Coins**\n"
                "   ↳ Permanent immunity from limit checks!\n\n"
                "🔹 `!purchase friendship` | **Cost: 500 Coins**\n"
                "   ↳ Bart treats you as a close companion.\n\n"
                "🔹 `!purchase ultimate` | **Cost: 1000 Coins**\n"
                "   ↳ Boost your limit to 100 instantly.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "*Type the exact phrase to purchase!*"
            )
            return

        if content_lower.startswith("!purchase "):
            if message.channel.id != ABILITIES_SHOP_CHANNEL_ID:
                await message.reply(f"❌ The abilities shop can only be accessed in <#{ABILITIES_SHOP_CHANNEL_ID}>")
                return
            
            item = content_lower[10:].strip()
            coins = get_coins(uid)

            shop_catalog = {
                "limit": 50,
                "vc": 100,
                "stealth": 250,
                "friendship": 500,
                "ultimate": 1000
            }

            if item not in shop_catalog:
                await message.reply("💀 That item doesn't exist. Use `!shop`.")
                return

            cost = shop_catalog[item]
            if coins < cost:
                await message.reply(f"❌ Not enough coins! Need **{cost}**, you have **{coins}**.")
                return

            if item == "limit":
                user_limits[uid] = user_limits.get(uid, DEFAULT_LIMIT) + 15
                add_coins(uid, -cost)
                save_economy()
                await message.reply(f"✅ Spent {cost} Coins. Limit increased by +15!")
            
            elif item == "vc":
                if check_permission(uid, "vc_access"):
                    await message.reply("❌ You already have VC access!")
                    return
                grant_permission(uid, "vc_access", True)
                add_coins(uid, -cost)
                await message.reply(f"✅ Spent {cost} Coins. You can now command `bart join the vc`.")

            elif item == "stealth":
                if check_permission(uid, "stealth_pass"):
                    await message.reply("❌ You already have Stealth Pass!")
                    return
                grant_permission(uid, "stealth_pass", True)
                add_coins(uid, -cost)
                await message.reply(f"✅ Spent {cost} Coins! Your account now has zero limit drain.")

            elif item == "friendship":
                if check_permission(uid, "friendship"):
                    await message.reply("❌ We are already homies!")
                    return
                grant_permission(uid, "friendship", True)
                add_coins(uid, -cost)
                await message.reply(f"✅ Spent {cost} Coins. We are officially tight now.")

            elif item == "ultimate":
                user_limits[uid] = 100
                add_coins(uid, -cost)
                save_economy()
                await message.reply(f"✅ Spent {cost} Coins. Your limit is now **100**!")

            return

        # ===================================================
        # ROLE SHOP SYSTEM - Only in designated channel
        # ===================================================

        if content_lower == "!buyrole":
            if message.channel.id != ROLES_SHOP_CHANNEL_ID:
                await message.reply(f"❌ The roles shop can only be accessed in <#{ROLES_SHOP_CHANNEL_ID}>")
                return
            
            if not role_shop:
                await message.reply("❌ No roles available for purchase.")
                return

            roles_str = "\n".join([f"**[{code}]** {info['role_name']} - **{info['price']} Coins**" for code, info in sorted(role_shop.items())])
            await message.reply(
                f"🛍️ **AVAILABLE ROLES FOR PURCHASE**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{roles_str}\n\n"
                f"*Type `!buy <code>` to purchase a role*"
            )
            return

        if content_lower.startswith("!buy "):
            # Check if this is a role purchase
            code = content[5:].strip()
            if code in role_shop:
                if message.channel.id != ROLES_SHOP_CHANNEL_ID:
                    await message.reply(f"❌ Role purchases can only be made in <#{ROLES_SHOP_CHANNEL_ID}>")
                    return
                
                role_info = role_shop[code]
                price = role_info["price"]
                role_id = role_info["role_id"]
                coins = get_coins(uid)

                if coins < price:
                    await message.reply(f"❌ Not enough coins! Need **{price}**, you have **{coins}**.")
                    return

                if uid not in user_inventory:
                    user_inventory[uid] = {}

                if code in user_inventory[uid]:
                    await message.reply(f"❌ You already own **{role_info['role_name']}**!")
                    return

                try:
                    member = message.guild.get_member(uid)
                    if not member:
                        await message.reply("❌ Error: Could not find you in the server.")
                        return

                    role = message.guild.get_role(role_id)
                    if not role:
                        await message.reply("❌ Error: Role not found in server.")
                        return

                    await member.add_roles(role, reason="Purchased from shop")
                    user_inventory[uid][code] = role_info.copy()
                    add_coins(uid, -price)
                    save_user_inventory()

                    await message.reply(f"✅ You purchased **{role_info['role_name']}** for **{price} Coins**! The role has been assigned to you.")
                except discord.Forbidden:
                    await message.reply("❌ Permission Error: I don't have permission to assign roles.")
                except Exception as e:
                    await message.reply(f"❌ Error: {str(e)}")
                return

        # ===================================================
        # SELLABLE ROLES SYSTEM - Only in designated channel
        # ===================================================

        if content_lower == "!sellroles":
            if message.channel.id != ROLES_SHOP_CHANNEL_ID:
                await message.reply(f"❌ Role selling can only be done in <#{ROLES_SHOP_CHANNEL_ID}>")
                return

            if uid not in user_inventory or not user_inventory[uid]:
                await message.reply("❌ Your inventory is empty.")
                return

            sellable_owned = []
            for code, info in user_inventory[uid].items():
                if code in sellable_roles:
                    sell_info = sellable_roles[code]
                    sellable_owned.append(f"**[{code}]** {info['role_name']} - Sell for: **{sell_info['sell_price']} Coins**")

            if not sellable_owned:
                await message.reply("❌ You have no sellable roles.")
                return

            roles_str = "\n".join(sellable_owned)
            await message.reply(
                f"💰 **YOUR SELLABLE ROLES**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{roles_str}\n\n"
                f"*Type `!sell <code>` to sell a role*"
            )
            return

        if content_lower.startswith("!sell "):
            if message.channel.id != ROLES_SHOP_CHANNEL_ID:
                await message.reply(f"❌ Role selling can only be done in <#{ROLES_SHOP_CHANNEL_ID}>")
                return

            code = content[6:].strip()
            
            if uid not in user_inventory or code not in user_inventory[uid]:
                await message.reply(f"❌ You don't own role `{code}`.")
                return

            if code not in sellable_roles:
                await message.reply(f"❌ Role `{code}` is not sellable.")
                return

            role_info = user_inventory[uid][code]
            sell_info = sellable_roles[code]
            sell_price = sell_info["sell_price"]

            try:
                member = message.guild.get_member(uid)
                role = message.guild.get_role(role_info["role_id"])
                if member and role:
                    await member.remove_roles(role, reason="Sold to shop")
            except:
                pass

            add_coins(uid, sell_price)
            del user_inventory[uid][code]
            save_user_inventory()

            await message.reply(f"✅ Sold **{role_info['role_name']}** for **{sell_price} Coins**!")
            return

        if content_lower == "!inventory":
            if uid not in user_inventory or not user_inventory[uid]:
                await message.reply("❌ Your inventory is empty.")
                return

            tradeable_roles_list = []
            sellable_roles_list = []

            for code, info in user_inventory[uid].items():
                role_str = f"**[{code}]** {info['role_name']}"
                if code in tradeable_roles:
                    tradeable_roles_list.append(role_str)
                if code in sellable_roles:
                    sell_price = sellable_roles[code]['sell_price']
                    sellable_roles_list.append(role_str + f" (Sell for: **{sell_price} Coins**)")

            inventory_text = "📦 **YOUR INVENTORY**\n━━━━━━━━━━━━━━━━━━━━━━\n"

            if tradeable_roles_list:
                inventory_text += f"**🔄 TRADEABLE ROLES:**\n" + "\n".join(tradeable_roles_list) + "\n\n"

            if sellable_roles_list:
                inventory_text += f"**💰 SELLABLE ROLES:**\n" + "\n".join(sellable_roles_list) + "\n"

            if not tradeable_roles_list and not sellable_roles_list:
                inventory_text += "No tradeable or sellable roles.\n"

            inventory_text += f"\n*Use `!trade @user`, `!sellroles`, `!sell <code>`*"
            await message.reply(inventory_text)
            return

        # ===================================================
        # TRADING SYSTEM - MULTIPLE ROLES & COINS - Only in designated channel
        # ===================================================

        if content_lower.startswith("!trade"):
            if message.channel.id != TRADE_CHANNEL_ID:
                await message.reply(f"❌ Trading can only be done in <#{TRADE_CHANNEL_ID}>")
                return
            
            if not message.mentions:
                await message.reply("⚠️ Usage: `!trade @user`")
                return
            
            target_member = message.mentions[0]
            if target_member.id == uid:
                await message.reply("💀 You cannot trade with yourself.")
                return
            if target_member.bot:
                await message.reply("❌ Bots cannot trade.")
                return

            # Get tradeable roles the target has
            target_tradeable_roles = []
            for code, trade_info in tradeable_roles.items():
                role = message.guild.get_role(trade_info["role_id"])
                if role and role in target_member.roles:
                    target_tradeable_roles.append((code, role, trade_info))

            if not target_tradeable_roles:
                await message.reply(f"❌ **{target_member.display_name}** has no tradeable roles.")
                return

            roles_list_str = "\n".join([f"• `{code}` - {info['role_name']}" for code, role, info in target_tradeable_roles])
            pending_takes[uid] = {"target_member": target_member, "guild": message.guild, "tradeable_roles": target_tradeable_roles}
            
            await message.reply(
                f"**Choose role(s) to take** from **{target_member.display_name}**:\n"
                f"{roles_list_str}\n\n"
                f"*Type `!take <code1> <code2> ...` to select multiple roles (space-separated).*"
            )
            return

        if content_lower.startswith("!take "):
            if uid not in pending_takes:
                await message.reply("❌ Run `!trade @user` first.")
                return

            code_queries = content[6:].strip().upper().split()
            trade_context = pending_takes[uid]
            target_member = trade_context["target_member"]
            guild = trade_context["guild"]
            tradeable_roles_list = trade_context["tradeable_roles"]

            matched_codes = []
            matched_roles = []
            matched_infos = []
            
            for code_query in code_queries:
                for code, role, info in tradeable_roles_list:
                    if code.upper() == code_query and code not in matched_codes:
                        matched_codes.append(code)
                        matched_roles.append(role)
                        matched_infos.append(info)
                        break

            if not matched_codes:
                await message.reply(f"❌ No valid role codes found.")
                return

            initiator_member = guild.get_member(uid)
            initiator_roles = [r for r in initiator_member.roles if not r.is_default()]
            if not initiator_roles:
                await message.reply("❌ You have no roles to offer back.")
                del pending_takes[uid]
                return

            # Get user's tradeable roles
            my_tradeable_roles = []
            for code, trade_info in tradeable_roles.items():
                role = guild.get_role(trade_info["role_id"])
                if role and role in initiator_member.roles:
                    my_tradeable_roles.append((code, role, trade_info))

            if not my_tradeable_roles:
                await message.reply("❌ You have no tradeable roles.")
                del pending_takes[uid]
                return

            my_roles_str = "\n".join([f"• `{code}` - {info['role_name']}" for code, role, info in my_tradeable_roles])
            matched_info_str = ", ".join([f"`{info['role_name']}`" for info in matched_infos])
            
            pending_gives[uid] = {
                "target_member": target_member,
                "guild": guild,
                "take_roles": matched_roles,
                "take_codes": matched_codes,
                "take_infos": matched_infos,
                "my_tradeable_roles": my_tradeable_roles
            }
            del pending_takes[uid]

            await message.reply(
                f"🔒 Selected: **{matched_info_str}**.\n"
                f"**What will you give?** Pick one or more of your tradeable roles, and optionally coins:\n"
                f"{my_roles_str}\n\n"
                f"*Type `!give <code1> <code2> ... [+coins]` (e.g., `!give 001 002 +50` for roles + 50 coins).*"
            )
            return

        if content_lower.startswith("!give "):
            if uid not in pending_gives:
                await message.reply("❌ Run `!trade @user` first.")
                return

            give_input = content[6:].strip()
            context = pending_gives[uid]
            target_member = context["target_member"]
            guild = context["guild"]
            take_roles = context["take_roles"]
            take_codes = context["take_codes"]
            take_infos = context["take_infos"]
            my_tradeable_roles = context["my_tradeable_roles"]

            # Parse coins if present (e.g., "001 002 +50")
            coin_amount = 0
            coin_direction = "to_target"  # by default, coins go to target
            code_queries = []
            parts = give_input.split()
            
            for part in parts:
                if part.startswith("+"):
                    try:
                        coin_amount = int(part[1:])
                    except:
                        pass
                else:
                    code_queries.append(part.upper())

            matched_give_codes = []
            matched_give_roles = []
            matched_give_infos = []
            
            for code_query in code_queries:
                for code, role, info in my_tradeable_roles:
                    if code.upper() == code_query and code not in matched_give_codes:
                        matched_give_codes.append(code)
                        matched_give_roles.append(role)
                        matched_give_infos.append(info)
                        break

            if not matched_give_codes and coin_amount == 0:
                await message.reply("❌ You must provide at least one role code or coins to trade.")
                return

            # Validate coins
            if coin_amount > 0:
                user_coins = get_coins(uid)
                if user_coins < coin_amount:
                    await message.reply(f"❌ Not enough coins! You have **{user_coins}** but trying to give **{coin_amount}**.")
                    return

            # Send trade proposal to target
            initiator_member = guild.get_member(uid)
            
            take_role_names = [info['role_name'] for info in take_infos]
            give_role_names = [info['role_name'] for info in matched_give_infos] if matched_give_infos else []
            
            active_trades[target_member.id] = {
                "initiator_id": uid,
                "channel_id": message.channel.id,
                "take_role_ids": [r.id for r in take_roles],
                "take_role_names": take_role_names,
                "give_role_ids": [r.id for r in matched_give_roles],
                "give_role_names": give_role_names,
                "guild_id": guild.id,
                "coin_amount": coin_amount,
                "coin_direction": coin_direction
            }
            del pending_gives[uid]

            # Build trade summary for DM
            trade_summary = f"📤 They will **TAKE**: {', '.join([f'`{name}`' for name in take_role_names])}\n"
            if give_role_names:
                trade_summary += f"📥 They will **GIVE**: {', '.join([f'`{name}`' for name in give_role_names])}\n"
            if coin_amount > 0:
                trade_summary += f"💰 They will **GIVE**: **+{coin_amount} Coins**\n"

            try:
                await target_member.send(
                    f"🔔 **Incoming Role Trade Request!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 **{initiator_member.display_name}** wants to trade with you.\n\n"
                    f"{trade_summary}"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👉 *Type `!agree` to confirm, or `!decline` to cancel.*"
                )
                await message.reply(f"✅ Trade proposal sent to **{target_member.display_name}**!")
            except discord.Forbidden:
                await message.reply(f"❌ Cannot send DM to **{target_member.display_name}**.")
                del active_trades[target_member.id]
            return

        if content_lower in ["!balance", "!wallet", "!cash"]:
            coins = get_coins(uid)
            current_bal = user_limits.get(uid, DEFAULT_LIMIT)
            stealth_perk = "Active" if check_permission(uid, "stealth_pass") else "Inactive"
            await message.reply(
                f"💰 **{message.author.display_name}'s Profile**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🪙 Bart Coins: **{coins}**\n"
                f"📉 Chat Limit Left: **{current_bal}**\n"
                f"🕶️ Stealth Pass: **{stealth_perk}**"
            )
            return

        # ===================================================
        # MAIN CHANNEL ONLY CHECK (Now AFTER command handling)
        # ===================================================
        if message.channel.id != TARGET_CHANNEL_ID:
            return

        LAST_CHANNEL = message.channel
        if hasattr(message.author, 'voice'):
            LAST_USER_VOICE_STATE = message.author.voice

        if LAST_CHANNEL.id not in channel_active_users:
            channel_active_users[LAST_CHANNEL.id] = []
        user_info = {"id": uid, "name": message.author.display_name}
        if user_info not in channel_active_users[LAST_CHANNEL.id]:
            channel_active_users[LAST_CHANNEL.id].append(user_info)
            if len(channel_active_users[LAST_CHANNEL.id]) > 10:
                channel_active_users[LAST_CHANNEL.id].pop(0)

        add_coins(uid, random.randint(1, 5))

        if content_lower == "bart join the vc":
            if uid == 1507727597428146317 or check_permission(uid, "vc_access"):
                await message.reply("bet")
                async def delayed_vc_entry():
                    await asyncio.sleep(5)
                    if message.author.voice and message.author.voice.channel:
                        await join_and_play_audio(message.author.voice.channel)
                asyncio.create_task(delayed_vc_entry())
                return  
            else:
                await message.reply("❌ Access Denied. Buy VC access with `!purchase vc`.")
                return

        if (message.mentions or message.role_mentions) and "bart" not in content_lower:
            return

        if uid not in user_limits:
            user_limits[uid] = DEFAULT_LIMIT
            save_economy()

        if not check_permission(uid, "stealth_pass") and uid not in AUTHORIZED_USERS and user_limits[uid] <= 0:
            if uid not in regeneration_trackers:
                regeneration_trackers.add(uid)
                asyncio.create_task(regenerate_user_limit(uid))
            await message.reply("❌ Out of limits! Check `!balance` or buy more with `!shop`.")
            return  

        if uid not in activated_users:
            activated_users[uid] = False

        if not activated_users[uid]:
            if content_lower.startswith("bart"):
                activated_users[uid] = True
                prompt = content[4:].strip()
            else:
                return
        else:
            prompt = content[4:].strip() if content_lower.startswith("bart") else content

        replied_context = f"User ID: {uid} | "
        if message.reference:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                replied_context += f"\nReplying to {ref.author.display_name} (<@{ref.author.id}>): {ref.content}"
            except:
                pass

        full_prompt = f"{prompt}\n{replied_context}"

        async with message.channel.typing():
            reply = ask_ai(
                OPENROUTER_API_KEY,
                full_prompt,
                uid in AUTHORIZED_USERS,
                message.channel.id,
                uid=uid
            )

        if not reply:
            return

        if uid not in AUTHORIZED_USERS and not check_permission(uid, "stealth_pass"):
            user_limits[uid] -= 1
            save_economy()
            if user_limits[uid] <= 0 and uid not in regeneration_trackers:
                regeneration_trackers.add(uid)
                asyncio.create_task(regenerate_user_limit(uid))

        channel_mem = get_memory(message.channel.id)
        channel_mem.append(f"{message.author.display_name}: {prompt}")
        channel_mem.append(f"Bart: {reply}")

        await message.reply(reply)

    bot.run(DISCORD_TOKEN)

# =========================
# CONTROL
# =========================

def run_bot():
    global bot_thread, running
    if running: return
    running = True
    bot_thread = threading.Thread(target=lambda: start_bot())
    bot_thread.start()

def stop_bot():
    global bot, running
    running = False
    if bot:
        try: asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
        except: pass

# =========================
# GUI FUNCTIONS
# =========================

def set_mode(mode):
    global BOT_MODE
    BOT_MODE = mode
    messagebox.showinfo("Mode", mode)

def toggle_stealth():
    global STEALTH_MODE
    STEALTH_MODE = not STEALTH_MODE
    messagebox.showinfo("Stealth", str(STEALTH_MODE))

def instant_say():
    msg = simpledialog.askstring("Say", "What should Bart say?")
    if msg and LAST_CHANNEL:
        asyncio.run_coroutine_threadsafe(LAST_CHANNEL.send(msg), bot.loop)

def spam_message():
    msg = simpledialog.askstring("Spam", "Message?")
    count = simpledialog.askinteger("Spam", "How many?")
    if not msg or not count or not LAST_CHANNEL: return
    async def spam():
        for _ in range(count):
            await LAST_CHANNEL.send(msg)
            await asyncio.sleep(0.4)
    asyncio.run_coroutine_threadsafe(spam(), bot.loop)

def reset_memory():
    memory.clear()
    messagebox.showinfo("Memory", "Cleared")

def gui_add_limit():
    try:
        uid = int(limit_user_entry.get())
        amount = int(limit_amount_entry.get())
        user_limits[uid] = user_limits.get(uid, DEFAULT_LIMIT) + amount
        save_economy()
        messagebox.showinfo("Limit", f"User {uid}: {user_limits[uid]}")
    except: messagebox.showerror("Error", "Invalid inputs.")

def gui_wipe_limits():
    if messagebox.askyesno("Warning", "Reset ALL limits?"):
        user_limits.clear()
        save_economy()
        messagebox.showinfo("Success", "Cleared.")

def gui_add_coins():
    try:
        uid = int(coin_user_entry.get())
        amount = int(coin_amount_entry.get())
        add_coins(uid, amount)
        messagebox.showinfo("Coins", f"User {uid}: {get_coins(uid)}")
    except: messagebox.showerror("Error", "Invalid inputs.")

def gui_wipe_economy():
    if messagebox.askyesno("Warning", "Wipe wallets?"):
        global user_wallets, user_permissions, user_limits
        user_wallets.clear()
        user_permissions.clear()
        user_limits.clear()
        save_economy()
        messagebox.showinfo("Success", "Cleared.")

def gui_update_personality():
    global BOT_PERSONALITY
    BOT_PERSONALITY = personality_text.get("1.0", tk.END).strip()
    if not BOT_PERSONALITY:
        BOT_PERSONALITY = "You are XBot. No AI assistant behavior."
    save_personality()
    messagebox.showinfo("Personality", "Updated!")

def gui_add_shop_role():
    try:
        code = shop_code_entry.get().strip()
        role_id_str = shop_role_id_entry.get().strip()
        role_name = shop_role_name_entry.get().strip()
        price_str = shop_price_entry.get().strip()
        
        if not all([code, role_id_str, role_name, price_str]):
            messagebox.showerror("Error", "All fields required.")
            return
        
        role_id = int(role_id_str)
        price = int(price_str)
        
        if code in role_shop:
            messagebox.showerror("Error", f"Code `{code}` exists.")
            return
        
        role_shop[code] = {
            "role_id": role_id,
            "role_name": role_name,
            "price": price,
            "tradeable": False,
            "sellable": False
        }
        save_role_shop()
        
        shop_code_entry.delete(0, tk.END)
        shop_role_id_entry.delete(0, tk.END)
        shop_role_name_entry.delete(0, tk.END)
        shop_price_entry.delete(0, tk.END)
        
        refresh_shop_list()
        messagebox.showinfo("Success", f"Added `{code}`")
    except ValueError:
        messagebox.showerror("Error", "Invalid values.")

def gui_remove_shop_role():
    try:
        code = remove_shop_entry.get().strip()
        if code not in role_shop:
            messagebox.showerror("Error", f"Code `{code}` not found.")
            return
        
        del role_shop[code]
        save_role_shop()
        remove_shop_entry.delete(0, tk.END)
        refresh_shop_list()
        messagebox.showinfo("Success", f"Removed `{code}`")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def refresh_shop_list():
    shop_listbox.delete(0, tk.END)
    for code, info in sorted(role_shop.items()):
        shop_listbox.insert(tk.END, f"[{code}] {info['role_name']} - {info['price']}c")

def gui_add_tradeable_role():
    try:
        code = trade_code_entry.get().strip()
        role_id_str = trade_role_id_entry.get().strip()
        role_name = trade_role_name_entry.get().strip()
        
        if not all([code, role_id_str, role_name]):
            messagebox.showerror("Error", "All fields required.")
            return
        
        role_id = int(role_id_str)
        
        if code in tradeable_roles:
            messagebox.showerror("Error", f"Code `{code}` exists.")
            return
        
        tradeable_roles[code] = {
            "role_id": role_id,
            "role_name": role_name,
            "tradeable": True
        }
        save_tradeable_roles()
        
        trade_code_entry.delete(0, tk.END)
        trade_role_id_entry.delete(0, tk.END)
        trade_role_name_entry.delete(0, tk.END)
        
        refresh_tradeable_list()
        messagebox.showinfo("Success", f"Added tradeable role `{code}`")
    except ValueError:
        messagebox.showerror("Error", "Invalid values.")

def gui_remove_tradeable_role():
    try:
        code = remove_trade_entry.get().strip()
        if code not in tradeable_roles:
            messagebox.showerror("Error", f"Code `{code}` not found.")
            return
        
        del tradeable_roles[code]
        save_tradeable_roles()
        remove_trade_entry.delete(0, tk.END)
        refresh_tradeable_list()
        messagebox.showinfo("Success", f"Removed tradeable role `{code}`")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def refresh_tradeable_list():
    tradeable_listbox.delete(0, tk.END)
    for code, info in sorted(tradeable_roles.items()):
        tradeable_listbox.insert(tk.END, f"[{code}] {info['role_name']}")

def gui_add_sellable_role():
    try:
        code = sellable_code_entry.get().strip()
        role_id_str = sellable_role_id_entry.get().strip()
        role_name = sellable_role_name_entry.get().strip()
        sell_price_str = sellable_price_entry.get().strip()
        
        if not all([code, role_id_str, role_name, sell_price_str]):
            messagebox.showerror("Error", "All fields required.")
            return
        
        role_id = int(role_id_str)
        sell_price = int(sell_price_str)
        
        if code in sellable_roles:
            messagebox.showerror("Error", f"Code `{code}` exists.")
            return
        
        sellable_roles[code] = {
            "role_id": role_id,
            "role_name": role_name,
            "sell_price": sell_price
        }
        save_sellable_roles()
        
        sellable_code_entry.delete(0, tk.END)
        sellable_role_id_entry.delete(0, tk.END)
        sellable_role_name_entry.delete(0, tk.END)
        sellable_price_entry.delete(0, tk.END)
        
        refresh_sellable_list()
        messagebox.showinfo("Success", f"Added sellable role `{code}`")
    except ValueError:
        messagebox.showerror("Error", "Invalid values.")

def gui_remove_sellable_role():
    try:
        code = remove_sellable_entry.get().strip()
        if code not in sellable_roles:
            messagebox.showerror("Error", f"Code `{code}` not found.")
            return
        
        del sellable_roles[code]
        save_sellable_roles()
        remove_sellable_entry.delete(0, tk.END)
        refresh_sellable_list()
        messagebox.showinfo("Success", f"Removed sellable role `{code}`")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def refresh_sellable_list():
    sellable_listbox.delete(0, tk.END)
    for code, info in sorted(sellable_roles.items()):
        sellable_listbox.insert(tk.END, f"[{code}] {info['role_name']} - ${info['sell_price']}")

# Initialize GUI with Scrollable Canvas
root = tk.Tk()
root.title("XBot Dashboard")
root.geometry("600x800")

# Create main frame with scrollbar
main_frame = tk.Frame(root)
main_frame.pack(fill="both", expand=True)

canvas = tk.Canvas(main_frame, highlightthickness=0)
scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

# Allow mouse wheel scrolling
def _on_mousewheel(event):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
canvas.bind_all("<MouseWheel>", _on_mousewheel)

# --- Bot Config ---
setup_frame = tk.LabelFrame(scrollable_frame, text=" Bot Config ")
setup_frame.pack(fill="x", padx=8, pady=3)

tk.Label(setup_frame, text="Token:", font=("Arial", 8)).grid(row=0, column=0, sticky="w", padx=3, pady=1)
token_entry = tk.Entry(setup_frame, width=35, show="*", font=("Arial", 8))
token_entry.grid(row=0, column=1, padx=3, pady=1)

tk.Label(setup_frame, text="API Key:", font=("Arial", 8)).grid(row=1, column=0, sticky="w", padx=3, pady=1)
key_entry = tk.Entry(setup_frame, width=35, show="*", font=("Arial", 8))
key_entry.grid(row=1, column=1, padx=3, pady=1)

def start_clicked():
    global DISCORD_TOKEN, OPENROUTER_API_KEY
    DISCORD_TOKEN = token_entry.get().strip()
    OPENROUTER_API_KEY = key_entry.get().strip()
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        messagebox.showerror("Error", "Missing fields.")
        return
    run_bot()
    messagebox.showinfo("Bot", "Started.")

btn_frame = tk.Frame(setup_frame)
btn_frame.grid(row=2, column=0, columnspan=2, pady=2)
tk.Button(btn_frame, text="Start", bg="green", fg="white", width=10, font=("Arial", 8), command=start_clicked).pack(side="left", padx=2)
tk.Button(btn_frame, text="Stop", bg="red", fg="white", width=10, font=("Arial", 8), command=stop_bot).pack(side="left", padx=2)

# --- Modes ---
mode_frame = tk.LabelFrame(scrollable_frame, text=" Modes ")
mode_frame.pack(fill="x", padx=8, pady=3)
tk.Button(mode_frame, text="Normal", width=10, font=("Arial", 8), command=lambda: set_mode("normal")).pack(side="left", expand=True, padx=1)
tk.Button(mode_frame, text="Chill", width=10, font=("Arial", 8), command=lambda: set_mode("chill")).pack(side="left", expand=True, padx=1)
tk.Button(mode_frame, text="Aggressive", width=10, font=("Arial", 8), command=lambda: set_mode("aggressive")).pack(side="left", expand=True, padx=1)

# --- Management ---
mgmt_frame = tk.Frame(scrollable_frame)
mgmt_frame.pack(fill="x", padx=8, pady=3)

lim_lf = tk.LabelFrame(mgmt_frame, text=" Limits ")
lim_lf.pack(side="left", fill="both", expand=True, padx=1)

tk.Label(lim_lf, text="UID:", font=("Arial", 8)).pack(anchor="w", padx=2)
limit_user_entry = tk.Entry(lim_lf, width=12, font=("Arial", 8))
limit_user_entry.pack(padx=2, pady=1)

tk.Label(lim_lf, text="Amt:", font=("Arial", 8)).pack(anchor="w", padx=2)
limit_amount_entry = tk.Entry(lim_lf, width=12, font=("Arial", 8))
limit_amount_entry.pack(padx=2, pady=1)

tk.Button(lim_lf, text="Update", bg="gray", fg="white", font=("Arial", 7), command=gui_add_limit).pack(fill="x", padx=2, pady=1)
tk.Button(lim_lf, text="Wipe", bg="orange", font=("Arial", 7), command=gui_wipe_limits).pack(fill="x", padx=2, pady=1)

econ_lf = tk.LabelFrame(mgmt_frame, text=" Coins ")
econ_lf.pack(side="right", fill="both", expand=True, padx=1)

tk.Label(econ_lf, text="UID:", font=("Arial", 8)).pack(anchor="w", padx=2)
coin_user_entry = tk.Entry(econ_lf, width=12, font=("Arial", 8))
coin_user_entry.pack(padx=2, pady=1)

tk.Label(econ_lf, text="Amt:", font=("Arial", 8)).pack(anchor="w", padx=2)
coin_amount_entry = tk.Entry(econ_lf, width=12, font=("Arial", 8))
coin_amount_entry.pack(padx=2, pady=1)

tk.Button(econ_lf, text="Add/Remove", bg="gold", font=("Arial", 7), command=gui_add_coins).pack(fill="x", padx=2, pady=1)
tk.Button(econ_lf, text="Wipe", bg="darkred", fg="white", font=("Arial", 7), command=gui_wipe_economy).pack(fill="x", padx=2, pady=1)

# --- PERSONALITY ---
pers_frame = tk.LabelFrame(scrollable_frame, text=" Bot Personality ")
pers_frame.pack(fill="x", padx=8, pady=3)

personality_text = tk.Text(pers_frame, height=4, width=60, font=("Arial", 8))
personality_text.insert("1.0", BOT_PERSONALITY)
personality_text.pack(padx=2, pady=2)

tk.Button(pers_frame, text="Save Personality", bg="purple", fg="white", font=("Arial", 8), command=gui_update_personality).pack(fill="x", padx=2, pady=1)

# --- ROLE SHOP ---
shop_frame = tk.LabelFrame(scrollable_frame, text=" Role Shop Manager ")
shop_frame.pack(fill="both", expand=True, padx=8, pady=3)

add_shop_frame = tk.LabelFrame(shop_frame, text=" Add Role ", font=("Arial", 8))
add_shop_frame.pack(fill="x", padx=2, pady=2)

tk.Label(add_shop_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
shop_code_entry = tk.Entry(add_shop_frame, width=12, font=("Arial", 8))
shop_code_entry.pack(padx=2, pady=1)

tk.Label(add_shop_frame, text="Role ID:", font=("Arial", 8)).pack(anchor="w", padx=2)
shop_role_id_entry = tk.Entry(add_shop_frame, width=12, font=("Arial", 8))
shop_role_id_entry.pack(padx=2, pady=1)

tk.Label(add_shop_frame, text="Role Name:", font=("Arial", 8)).pack(anchor="w", padx=2)
shop_role_name_entry = tk.Entry(add_shop_frame, width=12, font=("Arial", 8))
shop_role_name_entry.pack(padx=2, pady=1)

tk.Label(add_shop_frame, text="Price:", font=("Arial", 8)).pack(anchor="w", padx=2)
shop_price_entry = tk.Entry(add_shop_frame, width=12, font=("Arial", 8))
shop_price_entry.pack(padx=2, pady=1)

tk.Button(add_shop_frame, text="Add", bg="lightgreen", font=("Arial", 8), command=gui_add_shop_role).pack(fill="x", padx=2, pady=1)

remove_shop_frame = tk.LabelFrame(shop_frame, text=" Remove ", font=("Arial", 8))
remove_shop_frame.pack(fill="x", padx=2, pady=2)

tk.Label(remove_shop_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
remove_shop_entry = tk.Entry(remove_shop_frame, width=12, font=("Arial", 8))
remove_shop_entry.pack(padx=2, pady=1)

tk.Button(remove_shop_frame, text="Remove", bg="lightcoral", font=("Arial", 8), command=gui_remove_shop_role).pack(fill="x", padx=2, pady=1)

list_shop_frame = tk.LabelFrame(shop_frame, text=" Roles ", font=("Arial", 8))
list_shop_frame.pack(fill="both", expand=True, padx=2, pady=2)

shop_listbox = tk.Listbox(list_shop_frame, height=5, font=("Arial", 7))
shop_listbox.pack(fill="both", expand=True, padx=2, pady=2)

refresh_shop_list()

# --- TRADEABLE ROLES ---
trade_frame = tk.LabelFrame(scrollable_frame, text=" Tradeable Roles Manager ")
trade_frame.pack(fill="both", expand=True, padx=8, pady=3)

add_trade_frame = tk.LabelFrame(trade_frame, text=" Add Role ", font=("Arial", 8))
add_trade_frame.pack(fill="x", padx=2, pady=2)

tk.Label(add_trade_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
trade_code_entry = tk.Entry(add_trade_frame, width=12, font=("Arial", 8))
trade_code_entry.pack(padx=2, pady=1)

tk.Label(add_trade_frame, text="Role ID:", font=("Arial", 8)).pack(anchor="w", padx=2)
trade_role_id_entry = tk.Entry(add_trade_frame, width=12, font=("Arial", 8))
trade_role_id_entry.pack(padx=2, pady=1)

tk.Label(add_trade_frame, text="Role Name:", font=("Arial", 8)).pack(anchor="w", padx=2)
trade_role_name_entry = tk.Entry(add_trade_frame, width=12, font=("Arial", 8))
trade_role_name_entry.pack(padx=2, pady=1)

tk.Button(add_trade_frame, text="Add", bg="lightgreen", font=("Arial", 8), command=gui_add_tradeable_role).pack(fill="x", padx=2, pady=1)

remove_trade_frame = tk.LabelFrame(trade_frame, text=" Remove ", font=("Arial", 8))
remove_trade_frame.pack(fill="x", padx=2, pady=2)

tk.Label(remove_trade_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
remove_trade_entry = tk.Entry(remove_trade_frame, width=12, font=("Arial", 8))
remove_trade_entry.pack(padx=2, pady=1)

tk.Button(remove_trade_frame, text="Remove", bg="lightcoral", font=("Arial", 8), command=gui_remove_tradeable_role).pack(fill="x", padx=2, pady=1)

list_trade_frame = tk.LabelFrame(trade_frame, text=" Tradeable Roles ", font=("Arial", 8))
list_trade_frame.pack(fill="both", expand=True, padx=2, pady=2)

tradeable_listbox = tk.Listbox(list_trade_frame, height=5, font=("Arial", 7))
tradeable_listbox.pack(fill="both", expand=True, padx=2, pady=2)

refresh_tradeable_list()

# --- SELLABLE ROLES ---
sellable_frame = tk.LabelFrame(scrollable_frame, text=" Sellable Roles Manager ")
sellable_frame.pack(fill="both", expand=True, padx=8, pady=3)

add_sellable_frame = tk.LabelFrame(sellable_frame, text=" Add Role ", font=("Arial", 8))
add_sellable_frame.pack(fill="x", padx=2, pady=2)

tk.Label(add_sellable_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
sellable_code_entry = tk.Entry(add_sellable_frame, width=12, font=("Arial", 8))
sellable_code_entry.pack(padx=2, pady=1)

tk.Label(add_sellable_frame, text="Role ID:", font=("Arial", 8)).pack(anchor="w", padx=2)
sellable_role_id_entry = tk.Entry(add_sellable_frame, width=12, font=("Arial", 8))
sellable_role_id_entry.pack(padx=2, pady=1)

tk.Label(add_sellable_frame, text="Role Name:", font=("Arial", 8)).pack(anchor="w", padx=2)
sellable_role_name_entry = tk.Entry(add_sellable_frame, width=12, font=("Arial", 8))
sellable_role_name_entry.pack(padx=2, pady=1)

tk.Label(add_sellable_frame, text="Sell Price:", font=("Arial", 8)).pack(anchor="w", padx=2)
sellable_price_entry = tk.Entry(add_sellable_frame, width=12, font=("Arial", 8))
sellable_price_entry.pack(padx=2, pady=1)

tk.Button(add_sellable_frame, text="Add", bg="lightgreen", font=("Arial", 8), command=gui_add_sellable_role).pack(fill="x", padx=2, pady=1)

remove_sellable_frame = tk.LabelFrame(sellable_frame, text=" Remove ", font=("Arial", 8))
remove_sellable_frame.pack(fill="x", padx=2, pady=2)

tk.Label(remove_sellable_frame, text="Code:", font=("Arial", 8)).pack(anchor="w", padx=2)
remove_sellable_entry = tk.Entry(remove_sellable_frame, width=12, font=("Arial", 8))
remove_sellable_entry.pack(padx=2, pady=1)

tk.Button(remove_sellable_frame, text="Remove", bg="lightcoral", font=("Arial", 8), command=gui_remove_sellable_role).pack(fill="x", padx=2, pady=1)

list_sellable_frame = tk.LabelFrame(sellable_frame, text=" Sellable Roles ", font=("Arial", 8))
list_sellable_frame.pack(fill="both", expand=True, padx=2, pady=2)

sellable_listbox = tk.Listbox(list_sellable_frame, height=5, font=("Arial", 7))
sellable_listbox.pack(fill="both", expand=True, padx=2, pady=2)

refresh_sellable_list()

# --- Utilities ---
util_frame = tk.LabelFrame(scrollable_frame, text=" Utils ")
util_frame.pack(fill="x", padx=8, pady=3)
tk.Button(util_frame, text="Say", width=8, font=("Arial", 8), command=instant_say).pack(side="left", expand=True, padx=1)
tk.Button(util_frame, text="Spam", width=8, font=("Arial", 8), command=spam_message).pack(side="left", expand=True, padx=1)
tk.Button(util_frame, text="Stealth", width=8, font=("Arial", 8), command=toggle_stealth).pack(side="left", expand=True, padx=1)
tk.Button(util_frame, text="Reset Mem", width=8, font=("Arial", 8), command=reset_memory).pack(side="left", expand=True, padx=1)

root.mainloop()
