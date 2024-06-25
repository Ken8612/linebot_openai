from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import traceback
from datetime import datetime
import json

app = Flask(__name__)

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# File to store group amounts
GROUP_AMOUNTS_FILE = 'group_amounts.json'

# Load or initialize group amounts data
if os.path.exists(GROUP_AMOUNTS_FILE):
    with open(GROUP_AMOUNTS_FILE, 'r', encoding='utf-8') as f:
        group_amounts = json.load(f)
else:
    group_amounts = {}

# Save group amounts data to file
def save_group_amounts():
    with open(GROUP_AMOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(group_amounts, f, ensure_ascii=False, indent=4)

# Handle callback from LINE
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'

# Simple index page
@app.route("/", methods=['GET'])
def index():
    return 'Hello World! This is a LINE Bot.'

# Handle text messages
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = event.source.group_id if isinstance(event.source, Group) else None
    msg = event.message.text.strip()
    
    try:
        if msg.startswith('記錄金額 '):
            parts = msg.split(' ')
            if len(parts) == 3:
                date_str = parts[1]
                amount_str = parts[2].replace('$', '').replace('＄', '').strip()
                if amount_str.replace('.', '', 1).isdigit():  # Check if valid amount format
                    amount = float(amount_str)
                    date = datetime.strptime(date_str, '%y.%m.%d').date().isoformat()
                    
                    if group_id:
                        if group_id not in group_amounts:
                            group_amounts[group_id] = {}
                        
                        if user_id not in group_amounts[group_id]:
                            group_amounts[group_id][user_id] = []
                        
                        group_amounts[group_id][user_id].append({'date': date, 'amount': amount})
                        save_group_amounts()
                        reply_msg = f'已記錄 {date_str} 的金額 ${amount}'
                    else:
                        reply_msg = '此指令僅支援群組使用'
                else:
                    reply_msg = '金額格式錯誤，請輸入有效的數字'
            else:
                reply_msg = '指令格式錯誤，請使用「記錄金額 yyyy.mm.dd $金額」的格式'
        
        elif msg == '查詢總金額':
            if group_id and group_id in group_amounts:
                total_amount = sum(sum(record['amount'] for record in group_amounts[group_id][user_id]) for user_id in group_amounts[group_id])
                reply_msg = f'本群組總金額為 ${total_amount}'
            else:
                reply_msg = '目前沒有記錄任何金額'
        
        elif msg.startswith('刪除記錄 '):
            parts = msg.split(' ')
            if len(parts) == 2:
                date_str = parts[1]
                if group_id and group_id in group_amounts and user_id in group_amounts[group_id]:
                    group_amounts[group_id][user_id] = [record for record in group_amounts[group_id][user_id] if record['date'] != date_str]
                    save_group_amounts()
                    reply_msg = f'已刪除 {date_str} 的所有金額記錄'
                else:
                    reply_msg = f'找不到 {date_str} 的金額記錄'
            else:
                reply_msg = '指令格式錯誤，請使用「刪除記錄 yyyy.mm.dd」的格式'
        
        elif msg == '刪除所有記錄':
            if group_id and group_id in group_amounts:
                del group_amounts[group_id]
                save_group_amounts()
                reply_msg = '已刪除所有金額記錄'
            else:
                reply_msg = '目前沒有記錄任何金額'
        
        else:
            reply_msg = '請輸入有效指令，如「記錄金額 yyyy.mm.dd $金額」、「查詢總金額」、「刪除記錄 yyyy.mm.dd」或「刪除所有記錄」'
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
    
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
