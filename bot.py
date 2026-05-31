# bot.py - Fixed for Railway deployment
import os
import re
import logging
from datetime import datetime
from typing import Dict, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackContext
)
from pymongo import MongoClient
from dotenv import load_dotenv
import aiohttp
import asyncio

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_INVITE_LINK = os.getenv('CHANNEL_INVITE_LINK')
CHANNEL_ID = os.getenv('CHANNEL_ID')  # Keep as string for channel username or ID
API_URL = os.getenv('API_URL')
API_KEY = os.getenv('API_KEY')
MONGODB_URI = os.getenv('MONGODB_URI')
ADMIN_IDS = [int(admin_id.strip()) for admin_id in os.getenv('ADMIN_IDS', '').split(',') if admin_id.strip()]
OWNER_USERNAME = os.getenv('OWNER_USERNAME', 'DANGER_BOY_OP')

# Convert CHANNEL_ID to int if it's numeric, otherwise keep as string for username
try:
    CHANNEL_ID = int(CHANNEL_ID) if CHANNEL_ID and CHANNEL_ID.lstrip('-').isdigit() else CHANNEL_ID
except:
    pass

# Price plans (credits cost in INR)
PRICE_PLANS = {
    'basic': {'credits': 50, 'price': 10, 'bonus': 0},
    'standard': {'credits': 150, 'price': 25, 'bonus': 10},
    'premium': {'credits': 350, 'price': 50, 'bonus': 25},
    'pro': {'credits': 750, 'price': 100, 'bonus': 50}
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize MongoDB with a specific database name for this bot
DB_NAME = os.getenv('DB_NAME', 'number_info_bot')

# Handle MongoDB connection with error handling
try:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # Test the connection
    mongo_client.admin.command('ping')
    db = mongo_client[DB_NAME]
    users_collection = db['users']
    referrals_collection = db['referrals']
    logger.info("✅ MongoDB connected successfully")
except Exception as e:
    logger.error(f"❌ MongoDB connection failed: {e}")
    raise

def create_inline_keyboard():
    """Create consistent inline keyboard for all messages"""
    keyboard = [
        [InlineKeyboardButton("❤️ Join Our Channel", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton("👤 Contact Owner", url=f"https://t.me/{OWNER_USERNAME}")]
    ]
    return InlineKeyboardMarkup(keyboard)

class UserManager:
    @staticmethod
    def get_user(user_id: int) -> Optional[Dict]:
        return users_collection.find_one({'user_id': user_id})
    
    @staticmethod
    def create_user(user_id: int, username: str = None, referred_by: int = None) -> Dict:
        user_data = {
            'user_id': user_id,
            'username': username,
            'credits': 10,
            'joined_channel': False,
            'total_searches': 0,
            'total_referrals': 0,
            'created_at': datetime.utcnow(),
            'referred_by': referred_by
        }
        
        # Handle referral bonus
        if referred_by:
            referrer = users_collection.find_one({'user_id': referred_by})
            if referrer:
                users_collection.update_one(
                    {'user_id': referred_by},
                    {'$inc': {'credits': 5, 'total_referrals': 1}}
                )
                referrals_collection.insert_one({
                    'referrer_id': referred_by,
                    'referred_id': user_id,
                    'created_at': datetime.utcnow()
                })
        
        users_collection.insert_one(user_data)
        return user_data
    
    @staticmethod
    def update_credits(user_id: int, amount: int) -> bool:
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'credits': amount}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def add_credits(user_id: int, amount: int) -> bool:
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'credits': amount}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def update_joined_channel(user_id: int, joined: bool) -> bool:
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'joined_channel': joined}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def increment_searches(user_id: int):
        users_collection.update_one(
            {'user_id': user_id},
            {'$inc': {'total_searches': 1}}
        )

class APIManager:
    @staticmethod
    async def check_number(number: str) -> Dict:
        """Call the API using GET request to get number details"""
        api_url = os.getenv('API_URL')
        api_key = os.getenv('API_KEY')
        
        full_url = f"{api_url}?number={number}&key={api_key}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(full_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    data = await response.json()
                    return data
            except asyncio.TimeoutError:
                logger.error(f"API Timeout for number: {number}")
                return {'status': 'failed', 'error': 'Request timeout'}
            except Exception as e:
                logger.error(f"API Error: {e}")
                return {'status': 'failed', 'error': str(e)}

class MessageFormatter:
    @staticmethod
    def format_osint_result(data: Dict) -> str:
        """Format the OSINT result into a clean message"""
        if data.get('status') != 'success':
            return "❌ Failed to fetch details. Please try again."
        
        results = data.get('result', [])
        if not results:
            return "❌ No information found for this number."
        
        info = results[0]
        
        # Clean and format address
        address = info.get('address', 'N/A')
        address = address.replace('!!', '\n').replace('!', '\n')
        
        message = f"""📱 NUMBER DETAILS

📞 Basic Info:
• Number: {info.get('num', 'N/A')}
• Name: {info.get('name', 'N/A')}
• Father's Name: {info.get('fname', 'N/A')}
• Alternative No: {info.get('alt', 'N/A')}
• Circle: {info.get('circle', 'N/A')}
• Email: {info.get('email', 'Not Available')}

🆔 ID Info:
• Aadhar Number: {info.get('aadhar', 'N/A')}

🏠 Address:
{address}

✅ Search Completed - 1 credit deducted"""
        
        return message
    
    @staticmethod
    def format_price_list() -> str:
        """Format price list with discounts"""
        message = """💎 CREDIT PLANS

Basic Plan
• 20 Credits + 0 Bonus = 20 Total
• Price: ₹10

Standard Plan
• 50 Credits + 10 Bonus = 60 Total
• Price: ₹25

Premium Plan
• 100 Credits + 35 Bonus = 135 Total
• Price: ₹50

Pro Plan
• 200 Credits + 75 Bonus = 275 Total
• Price: ₹100

💳 Payment Methods:
• Accept Everything 
• Contact owner for Buy"""
        
        return message

class BotHandlers:
    @staticmethod
    async def is_admin(user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command - Shows different commands for users and admins"""
        user_id = update.effective_user.id
        is_admin_user = await BotHandlers.is_admin(user_id)
        
        if is_admin_user:
            # Admin help message
            help_msg = """🤖 Bot Help - Admin Panel

📌 User Commands:
/start - Register and get 10 free credits
/num <number> - Search any 10-digit number
/balance - Check your credit balance
/refer - Get your referral link
/plans - View price plans
/help - Show this help message

👑 Admin Commands:
/add <user_id> <credits> - Add credits to a user
/broadcast <message> - Send message to all users
/stats - View bot statistics

ℹ️ Info:
• Each search costs 1 credit
• Earn 5 credits per referral
• Contact owner for credit purchases

⚠️ Note: Users must join the channel to use the bot"""
        else:
            # Normal user help message
            help_msg = """🤖 Bot Help

📌 Available Commands:
/start - Register and get 10 free credits
/num <number> - Search any 10-digit number
/balance - Check your credit balance
/refer - Get your referral link
/plans - View price plans
/help - Show this help message

ℹ️ How it works:
• You get 10 free credits on registration
• Each number search costs 1 credit
• Earn 5 credits for each friend you refer
• Referral link: /refer

💡 Tips:
• Share your referral link to earn free credits
• Check /plans to purchase more credits
• Join our channel for updates

⚠️ Note: You must join our channel to use the bot!
Use the buttons below to join."""
        
        reply_markup = create_inline_keyboard()
        await update.message.reply_text(help_msg, parse_mode=None, reply_markup=reply_markup)
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with clean welcome message"""
        user = update.effective_user
        user_id = user.id
        
        # Check if user has referral code
        referred_by = None
        if context.args and len(context.args) > 0:
            try:
                referred_by = int(context.args[0])
                if referred_by == user_id:
                    referred_by = None
            except ValueError:
                pass
        
        # Check if user exists
        existing_user = UserManager.get_user(user_id)
        
        # Clean welcome message without any markdown symbols
        welcome_msg = f"""🔍 NUMBER INFORMATION BOT

Welcome {user.first_name}! I help you find details about any phone number.

━━━━━━━━━━━━━━━━━━━━
✨ What I Can Do
━━━━━━━━━━━━━━━━━━━━

🔹 Number Lookup - Get name, address, and more
🔹 Aadhar Info - Find linked Aadhar details  
🔹 Location Data - Get address and circle info
🔹 Alternate Numbers - Find associated numbers

━━━━━━━━━━━━━━━━━━━━
🎁 Free Credits
━━━━━━━━━━━━━━━━━━━━

✅ You get 10 FREE Credits on registration
✅ Each search costs only 1 credit
✅ Earn 5 credits for every friend you refer

"""

        if not existing_user:
            UserManager.create_user(user_id, user.username, referred_by)
            welcome_msg += f"""🎉 Account Created!
━━━━━━━━━━━━━━━━━━━━
💎 Credits: 10
🔍 Free Searches: 10

"""
            if referred_by:
                welcome_msg += """✅ +5 Referral Bonus Added!

"""
        else:
            welcome_msg += f"""👋 Welcome Back!
━━━━━━━━━━━━━━━━━━━━
💎 Your Credits: {existing_user.get('credits', 0)}

"""

        welcome_msg += """━━━━━━━━━━━━━━━━━━━━
📌 Quick Commands
━━━━━━━━━━━━━━━━━━━━

🔍 /num 9876543210 - Search any number
💰 /balance - Check your credits
👥 /refer - Get referral link
💎 /plans - View price plans
❓ /help - Show all commands

━━━━━━━━━━━━━━━━━━━━
⚠️ Important
━━━━━━━━━━━━━━━━━━━━

• You must join our channel to use this bot
• Each search costs 1 credit
• No refunds on failed searches

Click the buttons below to get started!"""
        
        reply_markup = create_inline_keyboard()
        await update.message.reply_text(welcome_msg, parse_mode=None, reply_markup=reply_markup)
    
    @staticmethod
    async def check_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Check if user has joined the channel"""
        user_id = update.effective_user.id
        
        try:
            # Handle both channel ID and username
            chat_id = CHANNEL_ID if isinstance(CHANNEL_ID, int) else f"@{CHANNEL_ID}" if not str(CHANNEL_ID).startswith('@') else CHANNEL_ID
            chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            
            if chat_member.status in ['member', 'administrator', 'creator']:
                UserManager.update_joined_channel(user_id, True)
                return True
            else:
                UserManager.update_joined_channel(user_id, False)
                keyboard = create_inline_keyboard()
                await update.message.reply_text(
                    "⚠️ Please join our channel first to use the bot!\n\nClick the buttons below to join and then try again.",
                    parse_mode=None,
                    reply_markup=keyboard
                )
                return False
        except Exception as e:
            logger.error(f"Channel check error: {e}")
            # If channel check fails, allow access (optional - remove if you want to enforce joining)
            return True
    
    @staticmethod
    async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /num command"""
        user_id = update.effective_user.id
        
        # Check if user has joined the channel
        joined = await BotHandlers.check_channel_join(update, context)
        if not joined:
            return
        
        # Check if number is provided
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ Usage: /num <10-digit-number>\n\nExample: /num 9876543210\n\nUse /help for more info.",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
            return
        
        number = context.args[0]
        
        # Validate number (10 digits)
        if not re.match(r'^\d{10}$', number):
            await update.message.reply_text(
                "❌ Invalid number!\nPlease provide a valid 10-digit phone number.\n\nExample: /num 9876543210",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
            return
        
        # Check user credits
        user = UserManager.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ Please use /start to register first.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        if user.get('credits', 0) < 1:
            await update.message.reply_text(
                f"❌ Insufficient credits!\n\n💳 Your balance: {user.get('credits', 0)} credits\n\nUse /plans to purchase more credits or /refer to earn free credits.\nUse /help for more info.",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "🔍 Processing...\nFetching details for your number.\n\nThis may take a few seconds...",
            parse_mode=None
        )
        
        # Call API
        api_response = await APIManager.check_number(number)
        
        # Check if API call was successful
        if api_response.get('status') == 'success':
            # Deduct 1 credit
            UserManager.update_credits(user_id, -1)
            UserManager.increment_searches(user_id)
            
            # Format and send result
            result_msg = MessageFormatter.format_osint_result(api_response)
            await processing_msg.edit_text(result_msg, parse_mode=None, reply_markup=create_inline_keyboard())
        else:
            # No credit deduction for failed attempts
            error_msg = api_response.get('error', 'Number not found')
            await processing_msg.edit_text(
                f"❌ Data not Found!\n\n📌 Number: {number}\n⚠️ Error: {error_msg}\n\n💳 No credits were deducted.\n💰 Your balance: {user.get('credits', 0)} credits\n\nUse /help for assistance.",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
    
    @staticmethod
    async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        user_id = update.effective_user.id
        
        # Check channel join
        joined = await BotHandlers.check_channel_join(update, context)
        if not joined:
            return
        
        user = UserManager.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ Please use /start to register first.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        balance_msg = f"""💰 YOUR BALANCE

━━━━━━━━━━━━━━━━━━━━
💎 Credits Available: {user.get('credits', 0)}
🔍 Total Searches Done: {user.get('total_searches', 0)}
👥 Friends Referred: {user.get('total_referrals', 0)}
━━━━━━━━━━━━━━━━━━━━

💡 Each search costs 1 credit
🆓 Get 5 free credits per referral

📌 Quick Actions:
/refer - Get your referral link
/plans - Buy more credits
/help - View all commands"""
        
        await update.message.reply_text(balance_msg, parse_mode=None, reply_markup=create_inline_keyboard())
    
    @staticmethod
    async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /refer command"""
        user_id = update.effective_user.id
        
        # Check channel join
        joined = await BotHandlers.check_channel_join(update, context)
        if not joined:
            return
        
        user = UserManager.get_user(user_id)
        if not user:
            await update.message.reply_text("❌ Please use /start to register first.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        refer_msg = f"""👥 REFERRAL PROGRAM

━━━━━━━━━━━━━━━━━━━━
💰 Earn 5 FREE Credits Per Referral!
━━━━━━━━━━━━━━━━━━━━

🔗 YOUR REFERRAL LINK:
{referral_link}

━━━━━━━━━━━━━━━━━━━━
📊 YOUR STATS
━━━━━━━━━━━━━━━━━━━━
• Friends Referred: {user.get('total_referrals', 0)}
• Credits Earned: {user.get('total_referrals', 0) * 5}

━━━━━━━━━━━━━━━━━━━━
✨ HOW IT WORKS
━━━━━━━━━━━━━━━━━━━━
1. Share your unique link with friends
2. They join using your link
3. You get 5 credits instantly!

💡 Share on WhatsApp, Telegram, or Instagram to earn more credits!"""
        
        await update.message.reply_text(refer_msg, parse_mode=None, reply_markup=create_inline_keyboard())
    
    @staticmethod
    async def plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /plans command"""
        user_id = update.effective_user.id
        
        # Check channel join
        joined = await BotHandlers.check_channel_join(update, context)
        if not joined:
            return
        
        plans_msg = MessageFormatter.format_price_list()
        plans_msg += "\n\n💡 Use /help for all available commands."
        reply_markup = create_inline_keyboard()
        
        await update.message.reply_text(plans_msg, parse_mode=None, reply_markup=reply_markup)
    
    # Admin Commands
    @staticmethod
    async def add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to add credits to a user - Admin only"""
        user_id = update.effective_user.id
        
        if not await BotHandlers.is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.\nUse /help to see available commands.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        if len(context.args) != 2:
            await update.message.reply_text(
                "❌ Usage: /add <user_id> <credits>\n\nExample: /add 123456789 50\n\nUse /help for admin commands.",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
            return
        
        try:
            target_user = int(context.args[0])
            credits = int(context.args[1])
            
            result = UserManager.add_credits(target_user, credits)
            
            if result:
                await update.message.reply_text(
                    f"✅ Success!\nAdded {credits} credits to user.",
                    parse_mode=None,
                    reply_markup=create_inline_keyboard()
                )
                
                # Notify the user
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"🎉 Credits Added!\n\n{credits} credits have been added to your account!\nUse /balance to check your new balance.\nUse /help for commands.",
                        parse_mode=None,
                        reply_markup=create_inline_keyboard()
                    )
                except:
                    pass
            else:
                await update.message.reply_text("❌ Failed to add credits. User might not exist.", parse_mode=None, reply_markup=create_inline_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or credits amount.", parse_mode=None, reply_markup=create_inline_keyboard())
    
    @staticmethod
    async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to broadcast message to all users"""
        user_id = update.effective_user.id
        
        if not await BotHandlers.is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.\nUse /help to see available commands.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ Usage: /broadcast <message>\n\nExample: /broadcast New update available!\n\nUse /help for admin commands.",
                parse_mode=None,
                reply_markup=create_inline_keyboard()
            )
            return
        
        broadcast_msg = ' '.join(context.args)
        
        # Get all users
        all_users = users_collection.find({}, {'user_id': 1})
        
        success_count = 0
        fail_count = 0
        
        status_msg = await update.message.reply_text("📢 Broadcasting message...", parse_mode=None)
        
        for user in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 Announcement\n\n{broadcast_msg}\n\nUse /help for bot commands.",
                    parse_mode=None,
                    reply_markup=create_inline_keyboard()
                )
                success_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to send to {user['user_id']}: {e}")
                fail_count += 1
        
        await status_msg.edit_text(
            f"✅ Broadcast Complete!\n\n✓ Sent: {success_count} users\n✗ Failed: {fail_count} users",
            parse_mode=None,
            reply_markup=create_inline_keyboard()
        )
    
    @staticmethod
    async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to view bot statistics - Admin only"""
        user_id = update.effective_user.id
        
        if not await BotHandlers.is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.\nUse /help to see available commands.", parse_mode=None, reply_markup=create_inline_keyboard())
            return
        
        total_users = users_collection.count_documents({})
        total_searches_result = users_collection.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$total_searches'}}}
        ])
        total_searches = list(total_searches_result)[0]['total'] if total_searches_result else 0
        
        total_credits_result = users_collection.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$credits'}}}
        ])
        total_credits = list(total_credits_result)[0]['total'] if total_credits_result else 0
        
        total_referrals_result = users_collection.aggregate([
            {'$group': {'_id': None, 'total': {'$sum': '$total_referrals'}}}
        ])
        total_referrals = list(total_referrals_result)[0]['total'] if total_referrals_result else 0
        
        stats_msg = f"""📊 BOT STATISTICS

━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
🔍 Total Searches: {total_searches}
💰 Total Credits: {total_credits}
👥 Total Referrals: {total_referrals}
━━━━━━━━━━━━━━━━━━━━

Use /help for admin commands."""
        
        await update.message.reply_text(stats_msg, parse_mode=None, reply_markup=create_inline_keyboard())

def main():
    """Main function to run the bot"""
    try:
        # Create application - This is the correct way in newer versions
        application = Application.builder().token(TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", BotHandlers.start))
        application.add_handler(CommandHandler("help", BotHandlers.help_command))
        application.add_handler(CommandHandler("num", BotHandlers.num_command))
        application.add_handler(CommandHandler("balance", BotHandlers.balance))
        application.add_handler(CommandHandler("refer", BotHandlers.refer))
        application.add_handler(CommandHandler("plans", BotHandlers.plans))
        
        # Admin command handlers
        application.add_handler(CommandHandler("add", BotHandlers.add_credits))
        application.add_handler(CommandHandler("broadcast", BotHandlers.broadcast))
        application.add_handler(CommandHandler("stats", BotHandlers.stats))
        
        # Start the bot
        print("🤖 Bot is starting...")
        print(f"📊 Using database: {DB_NAME}")
        print(f"👑 Admins: {ADMIN_IDS}")
        print(f"✅ Bot token: {TOKEN[:10]}...")
        
        # Start polling with error handling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()