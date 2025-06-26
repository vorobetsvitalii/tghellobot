import logging
import json
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    ChatJoinRequestHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# ===== Конфігурація =====
ADMIN_IDS = [1833581388, 7082906684]
TOKEN = "7733594700:AAGozxfK0w-tKRxGm5_sd_cpvF7QJ_xTDIs"
CLIENTS_FILE = "clients.json"
TEXT_FILE = "text.json"

# Стани для /edittext
EDIT_INIT_Q, EDIT_CONF_BTN, EDIT_MSG, EDIT_BUTTON, EDIT_CONFIRM = range(5)
# Стани для /broadcast
BCAST_MSG, BCAST_BUTTON, BCAST_CONFIRM = range(5, 8)

# ===== Ініціалізація файлів =====
def init_files():
    if not os.path.isfile(CLIENTS_FILE):
        with open(CLIENTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"clients": []}, f, ensure_ascii=False, indent=4)
    if not os.path.isfile(TEXT_FILE):
        with open(TEXT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "initial_question": "Бажаєш приєднатися до каналу?",
                "confirm_button": "Так",
                "message": "👋 Вітаємо! Ось ваші опції:",
                "buttons": []
            }, f, ensure_ascii=False, indent=4)

# ===== JSON утиліти =====
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ===== Перевірка прав =====
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            if update.message:
                await update.message.reply_text("🚫 Доступ заборонено.")
            elif update.callback_query:
                await update.callback_query.answer("🚫 Доступ заборонено.", show_alert=True)
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapper

# ===== Обробники приєднання =====
async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_json(TEXT_FILE)
    question = cfg.get('initial_question', '')
    confirm = cfg.get('confirm_button', '')
    context.user_data['awaiting_join'] = True
    kb = ReplyKeyboardMarkup([[confirm]], one_time_keyboard=True, resize_keyboard=True)
    await context.bot.send_message(
        chat_id=update.chat_join_request.from_user.id,
        text=question,
        reply_markup=kb
    )

async def handle_interest_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_join'):
        return

    cfg = load_json(TEXT_FILE)
    choice = update.message.text.strip()
    if choice == cfg['confirm_button']:
        clients = load_json(CLIENTS_FILE)
        uid = update.effective_user.id
        if not any(c['user_id'] == uid for c in clients['clients']):
            clients['clients'].append({'user_id': uid, 'username': update.effective_user.username or ''})
            save_json(CLIENTS_FILE, clients)

    # підготуємо одне повідомлення
    text = cfg['message']
    buttons = cfg.get('buttons', [])

    # знімаємо стару клавіатуру
    markup = ReplyKeyboardRemove()

    # якщо є inline-кнопки — будуємо InlineKeyboardMarkup
    if buttons:
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(b['text'], url=b['url'])] for b in buttons]
        )
        markup = inline_kb

    # відправляємо одне повідомлення з потрібним reply_markup
    await update.message.reply_text(text, reply_markup=markup)

    context.user_data.pop('awaiting_join', None)

# ===== Команди адміністраторів =====
@admin_only
async def list_clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clients = load_json(CLIENTS_FILE)['clients']
    if not clients:
        return await update.message.reply_text("Клієнтів немає.")
    lines = [f"Зареєстровано: {len(clients)}"] + [c['username'] or str(c['user_id']) for c in clients]
    await update.message.reply_text("\n".join(lines))

@admin_only
async def get_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load_json(TEXT_FILE)
    lines = [
        f"initial_question: {cfg.get('initial_question','')}",
        f"confirm_button: {cfg.get('confirm_button','')}",
        f"message: {cfg.get('message','')}"
    ]
    btns = cfg.get('buttons', [])
    lines.append("Buttons:")
    if btns:
        lines += [f"{i+1}. {b['text']} → {b['url']}" for i,b in enumerate(btns)]
    else:
        lines.append("(немає)")
    await update.message.reply_text("\n".join(lines))

# --- /edittext ---
@admin_only
async def edit_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 Редагування initial_question:\nНадішліть новий текст або /cancel.")
    return EDIT_INIT_Q

async def edit_init_q(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_initial_question'] = update.message.text.strip()
    await update.message.reply_text("Надішліть новий confirm_button.")
    return EDIT_CONF_BTN

async def edit_conf_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_confirm_button'] = update.message.text.strip()
    await update.message.reply_text("Надішліть новий message.")
    return EDIT_MSG

async def edit_text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_message'] = update.message.text.strip()
    context.user_data['new_buttons'] = []
    await update.message.reply_text("Надішліть кнопки Назва|https://url або /done.")
    return EDIT_BUTTON

async def edit_text_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.lower() == '/done':
        return await ask_edit_confirm(update, context)
    parts = txt.split('|', 1)
    if len(parts) == 2 and parts[1].startswith('http'):
        context.user_data['new_buttons'].append({'text': parts[0], 'url': parts[1]})
        await update.message.reply_text("Додано. Далі або /done.")
    else:
        await update.message.reply_text("Невірний формат")
    return EDIT_BUTTON

async def ask_edit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    lines = [
        f"initial_question: {data['new_initial_question']}",
        f"confirm_button: {data['new_confirm_button']}",
        f"message: {data['new_message']}"
    ]
    btns = data.get('new_buttons', [])
    lines.append("Buttons:")
    if btns:
        lines += [f"{i+1}. {b['text']}→{b['url']}" for i,b in enumerate(btns)]
    else:
        lines.append("(немає)")
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Так", callback_data='edit_yes'), InlineKeyboardButton("❌ Ні", callback_data='edit_no')]]
    )
    await update.message.reply_text("\n".join(lines), reply_markup=kb)
    return EDIT_CONFIRM

async def edit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == 'edit_yes':
        cfg = load_json(TEXT_FILE)
        cfg['initial_question'] = context.user_data['new_initial_question']
        cfg['confirm_button'] = context.user_data['new_confirm_button']
        cfg['message'] = context.user_data['new_message']
        cfg['buttons'] = context.user_data['new_buttons']
        save_json(TEXT_FILE, cfg)
        await q.edit_message_text("Збережено ✅")
    else:
        await q.edit_message_text("Скасовано ❌")
    context.user_data.clear()
    return ConversationHandler.END

# --- /broadcast ---
@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗣 Розсилка: надішліть текст або /cancel.")
    return BCAST_MSG

async def broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bc_message'] = update.message.text.strip()
    context.user_data['bc_buttons'] = []
    await update.message.reply_text("Надішліть кнопки Назва|https://url або /done.")
    return BCAST_BUTTON

async def broadcast_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.lower() == '/done':
        return await ask_bcast_confirm(update, context)
    parts = txt.split('|', 1)
    if len(parts) == 2 and parts[1].startswith('http'):
        context.user_data['bc_buttons'].append({'text': parts[0], 'url': parts[1]})
        await update.message.reply_text("Додано. Далі або /done.")
    else:
        await update.message.reply_text("Невірний формат")
    return BCAST_BUTTON

async def ask_bcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    lines = [f"Підтвердіть розсилку:\n{data['bc_message']}", "Кнопки:"]
    btns = data['bc_buttons']
    if btns:
        lines += [f"{i+1}. {b['text']}→{b['url']}" for i,b in enumerate(btns)]
    else:
        lines.append("(немає)")
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Так", callback_data='bcast_yes'), InlineKeyboardButton("❌ Ні", callback_data='bcast_no')]]
    )
    await update.message.reply_text("\n".join(lines), reply_markup=kb)
    return BCAST_CONFIRM

async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.from_user.id not in ADMIN_IDS:
        return ConversationHandler.END
    if q.data == 'bcast_yes':
        msg = context.user_data['bc_message']
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(b['text'], url=b['url'])] for b in context.user_data['bc_buttons']]
        ) if context.user_data['bc_buttons'] else None
        for c in load_json(CLIENTS_FILE)['clients']:
            await context.bot.send_message(chat_id=c['user_id'], text=msg, reply_markup=kb)
        await q.edit_message_text("Розсилка відправлена ✅")
    else:
        await q.edit_message_text("Скасовано ❌")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Скасовано ❌")
    context.user_data.clear()
    return ConversationHandler.END

# ===== Main =====
def main():
    init_files()
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    # Join flow
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interest_response), group=1)

    # Edittext conv
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("edittext", edit_text_start)],
        states={
            EDIT_INIT_Q:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_init_q)],
            EDIT_CONF_BTN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_conf_btn)],
            EDIT_MSG:       [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_msg)],
            EDIT_BUTTON:    [CommandHandler("done", ask_edit_confirm), MessageHandler(filters.TEXT & ~filters.COMMAND, edit_text_button)],
            EDIT_CONFIRM:   [CallbackQueryHandler(edit_confirm, pattern='^edit_')],
        },
        fallbacks=[CommandHandler("cancel", cancel)], allow_reentry=True
    )
    app.add_handler(edit_conv)

    # Broadcast conv
    bcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BCAST_MSG:      [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_msg)],
            BCAST_BUTTON:   [CommandHandler("done", ask_bcast_confirm), MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_button)],
            BCAST_CONFIRM:  [CallbackQueryHandler(broadcast_confirm, pattern='^bcast_')],
        },
        fallbacks=[CommandHandler("cancel", cancel)], allow_reentry=True
    )
    app.add_handler(bcast_conv)

    # Admin commands
    app.add_handler(CommandHandler("clients", list_clients_command))
    app.add_handler(CommandHandler("gettext", get_text_command))

    app.run_polling()

if __name__ == "__main__":
    main()