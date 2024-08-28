import os
from dotenv import load_dotenv
import telebot
from telebot.types import Message
import mysql.connector

# Load environment variables
load_dotenv()

# Initialize bot
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))

# Database connection
db = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME')
)
cursor = db.cursor(dictionary=True)

# Function to check if user is in database
def user_in_db(user_id, group_id):
    cursor.execute("SELECT * FROM user_groups WHERE user_id = %s AND group_id = %s", (user_id, group_id))
    return cursor.fetchone() is not None

# Function to add user to database
def add_user(user_id, first_name, username, group_id, group_name):
    cursor.execute("""
        INSERT INTO users (user_id, first_name, username) 
        VALUES (%s, %s, %s) 
        ON DUPLICATE KEY UPDATE first_name = %s, username = %s
    """, (user_id, first_name, username, first_name, username))
    
    cursor.execute("INSERT IGNORE INTO `groups` (group_id, name) VALUES (%s, %s)", (group_id, group_name))
    
    cursor.execute("INSERT IGNORE INTO user_groups (user_id, group_id) VALUES (%s, %s)", (user_id, group_id))
    
    db.commit()

def get_group_users(group_id):
    cursor.execute("""
        SELECT u.user_id, u.first_name, u.username
        FROM users u
        JOIN user_groups ug ON u.user_id = ug.user_id
        WHERE ug.group_id = %s
    """, (group_id,))
    return cursor.fetchall()

def mention_users(users):
    mentions = []
    for user in users:
        if user['username']:
            mentions.append(f"@{user['username']}")
        else:
            mentions.append(f"[{user['first_name']}](tg://user?id={user['user_id']})")
    return ' '.join(mentions)

# Handle all messages
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_message(message: Message):
    if message.chat.type in ['group', 'supergroup']:
        user_id = message.from_user.id
        first_name = message.from_user.first_name
        username = message.from_user.username
        group_id = message.chat.id
        group_name = message.chat.title

        add_user(user_id, first_name, username, group_id, group_name)

        lower_text = message.text.lower()
        
        if message.text.strip() == '/invocar' or message.text.strip() == '/invocar@invocacion_bot' or '@everyone' in lower_text or '@here' in lower_text:
            users = get_group_users(group_id)
            mentions = mention_users(users)
            try:
                bot.reply_to(message, f"{mentions}", parse_mode='Markdown')
            except:
                bot.reply_to(message, f"{mentions}")

# Start the bot
bot.polling()