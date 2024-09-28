import os
from dotenv import load_dotenv
import telebot
from telebot.types import Message
import mysql.connector

# Load environment variables
load_dotenv()

# Initialize bot
bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
ADMINISTRATOR = int(os.getenv('ADMINISTRATOR'))

# Create a connection pool
db_config = {
    "host": os.getenv('DB_HOST'),
    "user": os.getenv('DB_USER'),
    "password": os.getenv('DB_PASSWORD'),
    "database": os.getenv('DB_NAME'),
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=5,
    **db_config
)

def get_cursor():
    connection = connection_pool.get_connection()
    cursor = connection.cursor(dictionary=True)
    return connection, cursor

def close_connection(connection, cursor):
    cursor.close()
    connection.close()

def user_in_db(user_id, group_id):
    connection, cursor = get_cursor()
    try:
        cursor.execute("SELECT * FROM user_groups WHERE user_id = %s AND group_id = %s", (user_id, group_id))
        return cursor.fetchone() is not None
    finally:
        close_connection(connection, cursor)

def add_user(user_id, first_name, username, group_id, group_name):
    connection, cursor = get_cursor()
    try:
        cursor.execute("""
            INSERT INTO users (user_id, first_name, username) 
            VALUES (%s, %s, %s) 
            ON DUPLICATE KEY UPDATE first_name = %s, username = %s
        """, (user_id, first_name, username, first_name, username))
        
        cursor.execute("INSERT IGNORE INTO `groups` (group_id, name) VALUES (%s, %s)", (group_id, group_name))
        
        cursor.execute("INSERT IGNORE INTO user_groups (user_id, group_id) VALUES (%s, %s)", (user_id, group_id))
        
        connection.commit()
    finally:
        close_connection(connection, cursor)

def get_group_users(group_id):
    connection, cursor = get_cursor()
    try:
        cursor.execute("""
            SELECT u.user_id, u.first_name, u.username
            FROM users u
            JOIN user_groups ug ON u.user_id = ug.user_id
            WHERE ug.group_id = %s
        """, (group_id,))
        return cursor.fetchall()
    finally:
        close_connection(connection, cursor)

def mention_users(users):
    mentions = []
    needs_parsing = False
    for user in users:
        if user['username']:
            escaped_username = user['username'].replace('_', '\\_')
            mentions.append(f"@{escaped_username}")
        else:
            mentions.append(f"[{user['first_name']}](tg://user?id={user['user_id']})")
            needs_parsing = True
    return ' '.join(mentions), needs_parsing

def get_db_counts():
    connection, cursor = get_cursor()
    try:
        cursor.execute("SELECT COUNT(*) as user_count FROM users")
        user_count = cursor.fetchone()['user_count']
        
        cursor.execute("SELECT COUNT(*) as group_count FROM `groups`")
        group_count = cursor.fetchone()['group_count']
        
        return user_count, group_count
    finally:
        close_connection(connection, cursor)

@bot.message_handler(commands=['count'])
def handle_count(message: Message):
    if message.from_user.id == ADMINISTRATOR:
        user_count, group_count = get_db_counts()
        bot.reply_to(message, f"Database counts:\nUsers: {user_count}\nGroups: {group_count}")
    else:
        bot.reply_to(message, "You don't have permission to use this command.")

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
            mentions, needs_parsing = mention_users(users)
            if mentions:
                if needs_parsing:
                    mentions_escaped = mentions.replace('.', '\\.').replace('-', '\\-').replace('!', '\\!')
                    bot.reply_to(message, f"{mentions_escaped}", parse_mode='MarkdownV2')
                else:
                    bot.reply_to(message, f"{mentions}")
            else:
                bot.reply_to(message, "No users found in this group.")

# Start the bot
bot.polling()