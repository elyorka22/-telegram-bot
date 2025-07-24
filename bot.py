import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import tempfile
from translations import LANGUAGES, get_text
from users import user_manager

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO'))
)
logger = logging.getLogger(__name__)

# Initialize services
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is required")

def get_user_language(user_id: int) -> str:
    """Get user's language preference."""
    user = user_manager.get_user(user_id)
    if user:
        return user.get('language', 'en')
    return 'en'

def is_user_registered(user_id: int) -> bool:
    """Check if user is registered."""
    return user_manager.get_user(user_id) is not None

def require_registration(func):
    """Decorator to require user registration."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_user_registered(user_id):
            lang = get_user_language(user_id)
            await update.message.reply_text(
                f"{get_text('profile_not_registered', lang)}\n\n"
                f"{get_text('profile_register_first', lang)}"
            )
            return
        return await func(update, context)
    return wrapper

async def check_website_status():
    """Check if the website is running and accessible."""
    try:
        logger.info("Checking website status...")
        response = requests.get("https://amipumpkin.space/api/hashtags", timeout=10)
        logger.info(f"Website status check result: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Website status check failed: {e}")
        return False

async def send_message_to_website(text, user_id, username):
    """Send message to the website API."""
    try:
        # Extract hashtags from text
        hashtags = [word for word in text.split() if word.startswith('#')]
        category = hashtags[0] if hashtags else "#слова"  # Default category
        
        # Prepare data for API
        data = {
            "text": text,
            "hashtags": hashtags,
            "user_id": str(user_id),
            "username": username,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Send to website API
        response = requests.post(
            "https://amipumpkin.space/api/messages",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "Message sent successfully!"
        else:
            return False, f"Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Website is not running. Please start the website first."
    except Exception as e:
        logger.error(f"Error sending message to website: {e}")
        return False, f"Error: {str(e)}"

async def sync_user_to_backend(user_id: int):
    """Sync user data to backend website."""
    try:
        user = user_manager.get_user(user_id)
        if not user:
            return False, "User not found"
        
        # Prepare user data for backend
        user_data = {
            "user_id": str(user_id),
            "username": user.get('username'),
            "first_name": user.get('first_name'),
            "last_name": user.get('last_name'),
            "language": user.get('language', 'en'),
            "registered_at": user.get('registered_at'),
            "stats": user.get('stats', {})
        }
        
        # Send to backend API
        response = requests.post(
            "https://amipumpkin.space/api/users",
            json=user_data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code == 200:
            logger.info(f"User {user_id} synced to backend successfully")
            return True, "User synced successfully"
        else:
            logger.error(f"Backend sync failed for user {user_id}: {response.status_code}")
            return False, f"Backend sync failed: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        logger.error(f"Backend not available for user sync: {user_id}")
        return False, "Backend not available"
    except Exception as e:
        logger.error(f"Error syncing user to backend: {e}")
        return False, f"Sync error: {str(e)}"

async def create_hashtag(hashtag_name, description=""):
    """Create a new hashtag on the website."""
    try:
        data = {
            "name": hashtag_name,
            "description": description
        }
        
        response = requests.post(
            "https://amipumpkin.space/api/hashtags",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "Hashtag created successfully!"
        elif response.status_code == 409:
            return False, "Hashtag already exists!"
        else:
            return False, f"Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Website is not running. Please start the website first."
    except Exception as e:
        logger.error(f"Error creating hashtag: {e}")
        return False, f"Error: {str(e)}"

async def delete_hashtag(hashtag_name):
    """Delete a hashtag from the website."""
    try:
        response = requests.delete(
            f"https://amipumpkin.space/api/hashtags?name={hashtag_name}",
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "Hashtag deleted successfully!"
        elif response.status_code == 404:
            return False, "Hashtag not found!"
        else:
            return False, f"Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Website is not running. Please start the website first."
    except Exception as e:
        logger.error(f"Error deleting hashtag: {e}")
        return False, f"Error: {str(e)}"

async def get_hashtags():
    """Get all hashtags from the website."""
    try:
        response = requests.get(
            "https://amipumpkin.space/api/hashtags",
            timeout=15
        )
        
        if response.status_code == 200:
            hashtags = response.json()
            return True, hashtags
        else:
            return False, f"Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        return False, "Website is not running. Please start the website first."
    except Exception as e:
        logger.error(f"Error getting hashtags: {e}")
        return False, f"Error: {str(e)}"

async def get_words_by_category(category):
    """Get all words from a specific category."""
    try:
        logger.info(f"Fetching words for category: {category}")
        response = requests.get(
            "https://amipumpkin.space/api/messages",
            timeout=15
        )
        
        if response.status_code == 200:
            messages = response.json()
            logger.info(f"Received {len(messages)} total messages")
            # Filter messages by category
            category_words = [msg for msg in messages if msg.get('category') == category]
            logger.info(f"Found {len(category_words)} words in category {category}")
            return True, category_words
        else:
            logger.error(f"API returned status code: {response.status_code}")
            return False, f"Error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        logger.error("Connection error when fetching words by category")
        return False, "Website is not running. Please start the website first."
    except requests.exceptions.Timeout:
        logger.error("Timeout error when fetching words by category")
        return False, "Request timed out. Please try again."
    except Exception as e:
        logger.error(f"Error getting words by category: {e}")
        return False, f"Error: {str(e)}"

async def handle_create_hashtag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle creating hashtags."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_language(user_id)
    
    # Check if user is in create hashtag mode
    if context.user_data.get('awaiting_hashtag_create'):
        context.user_data['awaiting_hashtag_create'] = False
        
        # Parse hashtag name and description
        parts = text.split(' ', 1)
        hashtag_name = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        
        # Validate hashtag format
        if not hashtag_name.startswith('#'):
            await update.message.reply_text(
                f"{get_text('hashtag_must_start', lang)}\n\n"
                f"{get_text('hashtag_example', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
            return
        
        # Create hashtag
        success, message = await create_hashtag(hashtag_name, description)
        
        if success:
            # Increment hashtags created statistic
            user_manager.increment_stat(user_id, 'hashtags_created')
            
            await update.message.reply_text(
                f"{get_text('hashtag_created', lang)}\n\n"
                f"{get_text('hashtag_name', lang)} {hashtag_name}\n"
                f"{get_text('description', lang)} {description or get_text('no_description', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=get_main_keyboard(lang)
            )
    else:
        # First time - ask for hashtag
        context.user_data['awaiting_hashtag_create'] = True
        await update.message.reply_text(
            f"{get_text('create_hashtag_mode', lang)}\n\n"
            f"{get_text('send_hashtag', lang)}\n\n"
            f"{get_text('format', lang)}\n\n"
            f"{get_text('examples', lang)}\n"
            f"{get_text('new_hashtag_example', lang)}\n"
            f"{get_text('dictionary_example', lang)}\n"
            f"{get_text('grammar_example', lang)}",
            reply_markup=get_main_keyboard(lang)
        )

async def handle_delete_hashtag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle deleting hashtags."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_language(user_id)
    
    # Check if user is in delete hashtag mode
    if context.user_data.get('awaiting_hashtag_delete'):
        context.user_data['awaiting_hashtag_delete'] = False
        
        # Validate hashtag format
        if not text.startswith('#'):
            await update.message.reply_text(
                f"{get_text('hashtag_must_start', lang)}\n\n"
                f"{get_text('delete_example', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
            return
        
        # Delete hashtag
        success, message = await delete_hashtag(text)
        
        if success:
            # Increment hashtags deleted statistic
            user_manager.increment_stat(user_id, 'hashtags_deleted')
            
            await update.message.reply_text(
                f"{get_text('hashtag_deleted', lang)}\n\n"
                f"{get_text('deleted_hashtag', lang)} {text}",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=get_main_keyboard(lang)
            )
    else:
        # First time - show available hashtags and ask for one to delete
        success, result = await get_hashtags()
        
        if success:
            hashtags = result
            if hashtags:
                hashtag_list = "\n".join([f"• {h['name']}" for h in hashtags])
                await update.message.reply_text(
                    f"{get_text('delete_hashtag_mode', lang)}\n\n"
                    f"{get_text('available_hashtags', lang)}:\n{hashtag_list}\n\n"
                    f"{get_text('send_hashtag_to_delete', lang)}\n"
                    f"{get_text('delete_example', lang)}",
                    reply_markup=get_main_keyboard(lang)
                )
            else:
                await update.message.reply_text(
                    get_text('no_hashtags_found', lang),
                    reply_markup=get_main_keyboard(lang)
                )
        else:
            await update.message.reply_text(
                f"❌ {result}",
                reply_markup=get_main_keyboard(lang)
            )
        
        context.user_data['awaiting_hashtag_delete'] = True

async def handle_import_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle importing word lists as PDF."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    lang = get_user_language(user_id)
    
    # Check if user is in import mode
    if context.user_data.get('awaiting_category_import'):
        context.user_data['awaiting_category_import'] = False
        
        # Validate hashtag format
        if not text.startswith('#'):
            await update.message.reply_text(
                f"{get_text('category_must_start', lang)}\n\n"
                f"{get_text('import_example', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
            return
        
        # Get words from category
        success, result = await get_words_by_category(text)
        
        if success:
            words = result
            if words:
                # Generate PDF
                pdf_path = generate_pdf(words, text)
                
                if pdf_path:
                    try:
                        # Increment PDFs generated statistic
                        user_manager.increment_stat(user_id, 'pdfs_generated')
                        
                        # Send PDF file
                        with open(pdf_path, 'rb') as pdf_file:
                            await update.message.reply_document(
                                document=pdf_file,
                                filename=f"{text}_word_list.pdf",
                                caption=f"📄 {get_text('word_list_for', lang)} {text}\n\n"
                                       f"{get_text('total_words', lang)}: {len(words)}\n"
                                       f"{get_text('generated_on', lang)}: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                            )
                        
                        # Clean up temporary file
                        os.remove(pdf_path)
                        
                    except Exception as e:
                        logger.error(f"Error sending PDF: {e}")
                        await update.message.reply_text(
                            get_text('error_sending_pdf', lang),
                            reply_markup=get_main_keyboard(lang)
                        )
                else:
                    await update.message.reply_text(
                        get_text('error_generating_pdf', lang),
                        reply_markup=get_main_keyboard(lang)
                    )
            else:
                await update.message.reply_text(
                    f"{get_text('no_words_found', lang)} {text}.",
                    reply_markup=get_main_keyboard(lang)
                )
        else:
            await update.message.reply_text(
                f"❌ {result}",
                reply_markup=get_main_keyboard(lang)
            )
    else:
        # First time - show available categories and ask for one to import
        success, result = await get_hashtags()
        
        if success:
            hashtags = result
            if hashtags:
                hashtag_list = "\n".join([f"• {h['name']}" for h in hashtags])
                await update.message.reply_text(
                    f"{get_text('import_list_mode', lang)}\n\n"
                    f"{get_text('available_categories', lang)}:\n{hashtag_list}\n\n"
                    f"{get_text('send_category_to_import', lang)}\n"
                    f"{get_text('import_example', lang)}",
                    reply_markup=get_main_keyboard(lang)
                )
            else:
                await update.message.reply_text(
                    get_text('no_categories_found', lang),
                    reply_markup=get_main_keyboard(lang)
                )
        else:
            await update.message.reply_text(
                f"❌ {result}",
                reply_markup=get_main_keyboard(lang)
            )
        
        context.user_data['awaiting_category_import'] = True

async def handle_open_website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle opening the website."""
    user_id = update.effective_user.id
    lang = get_user_language(user_id)
    
    website_url = get_text('website_url', lang)
    
    await update.message.reply_text(
        f"{get_text('website_link', lang)}\n\n"
        f"🔗 {website_url}",
        reply_markup=get_main_keyboard(lang)
    )

async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user registration."""
    user = update.effective_user
    user_id = user.id
    
    # Check if user is already registered
    if is_user_registered(user_id):
        lang = get_user_language(user_id)
        await update.message.reply_text(
            get_text('user_already_registered', lang),
            reply_markup=get_main_keyboard(lang)
        )
        return
    
    # Register new user
    success = user_manager.register_user(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    if success:
        # Set default language to English for new users
        lang = 'en'
        user_manager.update_user_language(user_id, lang)
        
        # Try to sync user data to backend
        sync_success, sync_message = await sync_user_to_backend(user_id)
        
        welcome_message = f"{get_text('registration_successful', lang)}\n\n{get_text('registration_welcome', lang)}"
        
        if sync_success:
            welcome_message += f"\n\n✅ {get_text('user_synced_backend', lang) if 'user_synced_backend' in LANGUAGES[lang] else 'User data synced to website'}"
        else:
            welcome_message += f"\n\n⚠️ {get_text('user_sync_failed', lang) if 'user_sync_failed' in LANGUAGES[lang] else 'User data sync failed (website offline)'}"
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await update.message.reply_text("❌ Registration failed. Please try again.")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile."""
    user_id = update.effective_user.id
    
    if not is_user_registered(user_id):
        lang = get_user_language(user_id)
        await update.message.reply_text(
            f"{get_text('profile_not_registered', lang)}\n\n"
            f"{get_text('profile_register_first', lang)}"
        )
        return
    
    # Get user profile
    profile = user_manager.get_user_profile(user_id)
    lang = profile.get('language', 'en')
    
    # Format registration date
    registered_date = datetime.fromisoformat(profile['registered_at'])
    formatted_date = registered_date.strftime('%Y-%m-%d %H:%M')
    
    # Build profile message
    profile_message = f"{get_text('profile_title', lang)}\n\n"
    profile_message += f"{get_text('profile_username', lang)} {profile['username']}\n"
    profile_message += f"{get_text('profile_name', lang)} {profile['first_name']}"
    if profile['last_name']:
        profile_message += f" {profile['last_name']}"
    profile_message += f"\n{get_text('profile_language', lang)} {profile['language'].upper()}\n"
    profile_message += f"{get_text('profile_registered', lang)} {formatted_date}\n"
    profile_message += f"({profile['days_registered']} {get_text('profile_days', lang)})\n\n"
    
    # Add statistics
    stats = profile['stats']
    profile_message += f"{get_text('profile_stats', lang)}\n"
    profile_message += f"• {get_text('profile_words_saved', lang)}: {stats['words_saved']}\n"
    profile_message += f"• {get_text('profile_hashtags_created', lang)}: {stats['hashtags_created']}\n"
    profile_message += f"• {get_text('profile_hashtags_deleted', lang)}: {stats['hashtags_deleted']}\n"
    profile_message += f"• {get_text('profile_pdfs_generated', lang)}: {stats['pdfs_generated']}\n"
    profile_message += f"• {get_text('profile_total_messages', lang)}: {stats['total_messages']}"
    
    await update.message.reply_text(
        profile_message,
        reply_markup=get_main_keyboard(lang)
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons."""
    query = update.callback_query
    
    # Answer the callback query to remove the loading state
    await query.answer()
    
    # Handle different callback data if needed in the future
    # For now, we only have website button which opens URL directly
    # No additional action needed as the URL opens automatically

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Check if user is registered
    if not is_user_registered(user_id):
        lang = 'en'
        await update.message.reply_text(
            f"{get_text('profile_not_registered', lang)}\n\n"
            f"{get_text('profile_register_first', lang)}"
        )
        return
    
    # Update user activity
    user_manager.update_user_activity(user_id)
    
    # Check if user is in language selection mode
    if context.user_data.get('awaiting_language'):
        context.user_data['awaiting_language'] = False
        
        # Get user's language choice
        lang_choice = text.lower().strip()
        
        if lang_choice in ['1', 'english', 'en', 'английский']:
            user_manager.update_user_language(user_id, 'en')
            await update.message.reply_text(
                get_text('language_set_english', 'en'),
                reply_markup=get_main_keyboard('en')
            )
        elif lang_choice in ['2', 'русский', 'ru', 'russian']:
            user_manager.update_user_language(user_id, 'ru')
            await update.message.reply_text(
                get_text('language_set_russian', 'ru'),
                reply_markup=get_main_keyboard('ru')
            )
        elif lang_choice in ['3', 'узбекский', 'uz', 'uzbek', 'o\'zbek']:
            user_manager.update_user_language(user_id, 'uz')
            await update.message.reply_text(
                get_text('language_set_uzbek', 'uz'),
                reply_markup=get_main_keyboard('uz')
            )
        else:
            await update.message.reply_text(
                f"{get_text('invalid_language_choice', 'en')}\n"
                f"{get_text('invalid_language_choice', 'ru')}\n"
                f"{get_text('invalid_language_choice', 'uz')}",
                reply_markup=get_main_keyboard()
            )
    else:
        # First time - show language options
        context.user_data['awaiting_language'] = True
        await update.message.reply_text(
            f"{get_text('choose_language', 'en')} / {get_text('choose_language', 'ru')} / {get_text('choose_language', 'uz')}:\n\n"
            f"1. {get_text('english_option', 'en')} / {get_text('english_option', 'ru')} / {get_text('english_option', 'uz')}\n"
            f"2. {get_text('russian_option', 'en')} / {get_text('russian_option', 'ru')} / {get_text('russian_option', 'uz')}\n"
            f"3. {get_text('uzbek_option', 'en')} / {get_text('uzbek_option', 'ru')} / {get_text('uzbek_option', 'uz')}\n\n"
            f"{get_text('send_number_or_name', 'en')}\n"
            f"{get_text('send_number_or_name', 'ru')}\n"
            f"{get_text('send_number_or_name', 'uz')}",
            reply_markup=get_main_keyboard()
        )

def get_main_keyboard(lang='en'):
    """Get the main keyboard layout."""
    keyboard = [
        [KeyboardButton(get_text('create_hashtag', lang)), KeyboardButton(get_text('delete_hashtag', lang))],
        [KeyboardButton(get_text('import_list', lang)), KeyboardButton(get_text('help', lang))],
        [KeyboardButton(get_text('language_button', lang)), KeyboardButton(get_text('open_website', lang))],
        [KeyboardButton(get_text('profile', lang)), KeyboardButton(get_text('register', lang))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_website_inline_keyboard(lang='en'):
    """Get inline keyboard with website button."""
    keyboard = [
        [InlineKeyboardButton(get_text('open_website', lang), url=get_text('website_url', lang))]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Check if user is registered
    if not is_user_registered(user_id):
        lang = 'en'  # Default language for new users
        welcome_message = (
            f"{get_text('welcome', lang)}\n\n"
            f"{get_text('welcome_new_user', lang)}"
        )
        await update.message.reply_text(welcome_message)
        return
    
    # Get user's language preference
    lang = get_user_language(user_id)
    
    # Update user activity
    user_manager.update_user_activity(user_id)
    
    welcome_message = (
        f"{get_text('welcome', lang)}\n\n"
        f"{get_text('welcome_desc', lang)}\n\n"
        f"{get_text('hashtag_help', lang)}\n"
        f"• #заметка - {get_text('notes', lang)}\n"
        f"• #разборка - {get_text('grammar_analysis', lang)}\n"
        f"• #фразы - {get_text('useful_phrases', lang)}\n"
        f"• #слова - {get_text('new_words', lang)}\n"
        f"• #грамматика - {get_text('grammar_rules', lang)}\n\n"
        f"{get_text('example', lang)}"
    )
    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard(lang))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user_id = update.effective_user.id
    
    # Check if user is registered
    if not is_user_registered(user_id):
        lang = 'en'
        await update.message.reply_text(
            f"{get_text('profile_not_registered', lang)}\n\n"
            f"{get_text('profile_register_first', lang)}"
        )
        return
    
    # Get user's language preference
    lang = get_user_language(user_id)
    
    # Update user activity
    user_manager.update_user_activity(user_id)
    
    help_message = (
        f"{get_text('welcome', lang)}\n\n"
        f"{get_text('welcome_desc', lang)}\n\n"
        f"{get_text('hashtag_help', lang)}\n"
        f"• #заметка - {get_text('notes', lang)}\n"
        f"• #разборка - {get_text('grammar_analysis', lang)}\n"
        f"• #фразы - {get_text('useful_phrases', lang)}\n"
        f"• #слова - {get_text('new_words', lang)}\n"
        f"• #грамматика - {get_text('grammar_rules', lang)}\n\n"
        f"{get_text('example', lang)}"
    )
    await update.message.reply_text(help_message, reply_markup=get_main_keyboard(lang))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages and menu button presses."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    lower_text = text.lower()
    
    # Check if user is registered for most functions
    if not is_user_registered(user_id):
        lang = 'en'
        if lower_text == get_text("register", lang).lower():
            await register_command(update, context)
            return
        else:
            await update.message.reply_text(
                f"{get_text('profile_not_registered', lang)}\n\n"
                f"{get_text('profile_register_first', lang)}"
            )
            return
    
    # Get user's language preference
    lang = get_user_language(user_id)
    
    # Update user activity
    user_manager.update_user_activity(user_id)

    # Check if user is in create hashtag mode
    if context.user_data.get('awaiting_hashtag_create'):
        await handle_create_hashtag(update, context)
        return

    # Check if user is in delete hashtag mode
    if context.user_data.get('awaiting_hashtag_delete'):
        await handle_delete_hashtag(update, context)
        return

    # Check if user is in import mode
    if context.user_data.get('awaiting_category_import'):
        await handle_import_list(update, context)
        return

    # Check if user is in language selection mode
    if context.user_data.get('awaiting_language'):
        await handle_language_selection(update, context)
        return

    # Check if message contains hashtags - automatically send to website
    hashtags = [word for word in text.split() if word.startswith('#')]
    if hashtags:
        # Send message to website
        success, message = await send_message_to_website(
            text, 
            update.effective_user.id, 
            update.effective_user.username or update.effective_user.first_name
        )
        
        if success:
            # Increment words saved statistic
            user_manager.increment_stat(user_id, 'words_saved')
            
            await update.message.reply_text(
                f"{get_text('word_saved', lang)}\n\n"
                f"{get_text('word', lang)}: {text}\n"
                f"{get_text('category', lang)}: {hashtags[0]}\n\n"
                f"{get_text('check_website', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
        else:
            await update.message.reply_text(
                f"❌ {message}\n\n"
                f"{get_text('website_not_running', lang)}",
                reply_markup=get_main_keyboard(lang)
            )
        return

    if lower_text == get_text("help", lang).lower():
        await help_command(update, context)
    elif lower_text == get_text("create_hashtag", lang).lower():
        await handle_create_hashtag(update, context)
    elif lower_text == get_text("delete_hashtag", lang).lower():
        await handle_delete_hashtag(update, context)
    elif lower_text == get_text("import_list", lang).lower():
        await handle_import_list(update, context)
    elif lower_text == get_text("language_button", lang).lower():
        await handle_language_selection(update, context)
    elif lower_text == get_text("open_website", lang).lower():
        await handle_open_website(update, context)
    elif lower_text == get_text("profile", lang).lower():
        await profile_command(update, context)
    elif lower_text == get_text("register", lang).lower():
        await register_command(update, context)
    else:
        # If message doesn't contain hashtags, remind user about hashtag usage
        await update.message.reply_text(
            f"{get_text('send_hashtag_message', lang)}\n\n"
            f"{get_text('examples', lang)}:\n"
            f"{get_text('examples_' + lang, lang) if f'examples_{lang}' in LANGUAGES[lang] else get_text('examples_en', lang)}",
            reply_markup=get_main_keyboard(lang)
        )

def generate_pdf(words, category_name):
    """Generate a PDF file with words from a category."""
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            pdf_path = tmp_file.name
        
        # Create PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        
        # Use simple, built-in fonts that work well
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=1,
            textColor=blue,
            fontName='Times-Bold'
        )
        
        word_style = ParagraphStyle(
            'Word',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=8,
            leftIndent=20,
            fontName='Times-Roman'
        )
        
        translation_style = ParagraphStyle(
            'Translation',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=10,
            leftIndent=40,
            textColor=black,
            fontName='Times-Italic'
        )
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=1,
            fontName='Times-Roman'
        )
        
        # Build content
        story = []
        
        # Title
        title = Paragraph(f"{category_name} - Word List", title_style)
        story.append(title)
        story.append(Spacer(1, 15))
        
        # Words
        for i, word_data in enumerate(words, 1):
            # Clean text
            word_text = word_data.get('text', '').replace(f" {category_name}", '').strip()
            word_text = word_text.replace('📚', '').replace('📄', '').replace('🏷️', '').replace('🗑️', '').replace('❓', '').replace('✅', '').replace('❌', '').replace('ℹ️', '').replace('💡', '')
            
            if word_text:
                word_paragraph = Paragraph(f"{i}. {word_text}", word_style)
                story.append(word_paragraph)
                
                # Translation
                translation = word_data.get('translation', '')
                if translation:
                    translation = translation.replace('📚', '').replace('📄', '').replace('🏷️', '').replace('🗑️', '').replace('❓', '').replace('✅', '').replace('❌', '').replace('ℹ️', '').replace('💡', '')
                    if translation.strip():
                        translation_paragraph = Paragraph(f"   → {translation.strip()}", translation_style)
                        story.append(translation_paragraph)
                
                story.append(Spacer(1, 3))
        
        # Footer
        footer = Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Words: {len(words)}", 
            footer_style
        )
        story.append(Spacer(1, 15))
        story.append(footer)
        
        # Build PDF
        doc.build(story)
        
        return pdf_path
        
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return None

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("register", register_command))
    application.add_handler(CommandHandler("profile", profile_command))
    
    # Add message handler for menu buttons
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 