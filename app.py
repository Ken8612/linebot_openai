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

# 記錄群組的日期與金額
group_amounts = {}

# 檢查是否有儲存過的金額記錄檔案，若有則載入
if os.path.exists('group_amounts.json'):
    with open('group_amounts.json', 'r', encoding='utf-8') as f:
        group_amounts = json.load(f)

# 儲存金額記錄到檔案
def save_group_amounts():
    with open('group_amounts.json', 'w', encoding='utf-8') as f:
        json.dump(group_amounts, f, ensure_ascii=False, indent=4)

# 處理訊息
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/", methods=['GET'])
def index():
    return 'Hello World! This is a LINE Bot.'

# 處理訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text
    user_id = event.source.user_id
    group_id = event.source.group_id
    
    try:
        if msg.startswith('記錄金額 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 3:
                    date_str = parts[1]
                    amount_str = parts[2].replace('$', '').replace('＄', '').strip()
                    if amount_str.replace('.', '', 1).isdigit():  # 檢查是否為有效的金額格式
                        amount = float(amount_str)
                        date = datetime.strptime(date_str, '%Y.%m.%d').date()  # 使用 %Y 修正年份格式
                        if group_id in group_amounts:
                            if user_id in group_amounts[group_id]:
                                group_amounts[group_id][user_id].append((date_str, amount))
                            else:
                                group_amounts[group_id][user_id] = [(date_str, amount)]
                        else:
                            group_amounts[group_id] = {user_id: [(date_str, amount)]}
                        success_msgs.append(f'已記錄 {date_str} 的貨款 {amount}')
                    else:
                        error_msgs.append(f'金額格式錯誤: {amount_str}')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                reply_msg = '\n'.join(success_msgs)
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg == '查詢總金額':
            if group_id in group_amounts and len(group_amounts[group_id]) > 0:
                total_amount = sum(amount for user_id in group_amounts[group_id] for date_str, amount in group_amounts[group_id][user_id])
                records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id] for date_str, amount in group_amounts[group_id][user_id])
                reply_msg = f'總貨款: ${total_amount}\n記錄:\n{records}'
            else:
                reply_msg = '目前沒有記錄任何貨款'
        
        elif msg.startswith('刪除金額 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 2:
                    date_str = parts[1]
                    if group_id in group_amounts and user_id in group_amounts[group_id]:
                        group_amounts[group_id][user_id] = [(d, a) for d, a in group_amounts[group_id][user_id] if d != date_str]
                        success_msgs.append(f'已刪除 {date_str} 的所有貨款記錄')
                    else:
                        error_msgs.append(f'找不到 {date_str} 的貨款記錄')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                reply_msg = '\n'.join(success_msgs)
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg == '刪除所有金額':
            if group_id in group_amounts:
                del group_amounts[group_id]
                save_group_amounts()  # 儲存更新後的金額記錄
                reply_msg = '已刪除所有金額貨款'
            else:
                reply_msg = '目前沒有記錄任何金額'
        
        else:
            reply_msg = '請輸入有效指令，如「記錄金額 yyyy.mm.dd $金額」、「查詢總金額」、「刪除金額 yyyy.mm.dd」或「刪除所有金額」'

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
