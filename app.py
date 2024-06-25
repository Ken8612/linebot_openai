from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import traceback
from datetime import datetime

app = Flask(__name__)

# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# 記錄群組的日期與金額
group_amounts = {}

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
            parts = msg.split(' ')
            if len(parts) == 3:
                date_str = parts[1]
                amount_str = parts[2].replace('$', '').replace('＄', '').strip()
                if amount_str.replace('.', '', 1).isdigit():  # 檢查是否為有效的金額格式
                    amount = float(amount_str)
                    date = datetime.strptime(date_str, '%Y.%m.%d').date()  # 使用 %Y 修正年份格式
                    if group_id in group_amounts:
                        if user_id in group_amounts[group_id]:
                            group_amounts[group_id][user_id].append((date, amount))
                        else:
                            group_amounts[group_id][user_id] = [(date, amount)]
                    else:
                        group_amounts[group_id] = {user_id: [(date, amount)]}
                    reply_msg = f'已記錄 {date_str} 的金額 {amount}'
                else:
                    reply_msg = '金額格式錯誤，請輸入有效的數字'
            else:
                reply_msg = '指令格式錯誤，請使用「記錄金額 yyyy.mm.dd $金額」的格式'
        elif msg == '查詢總金額':
            if group_id in group_amounts and len(group_amounts[group_id]) > 0:
                total_amount = sum(amount for user_id in group_amounts[group_id] for _, amount in group_amounts[group_id][user_id])
                records = '\n'.join(f'{date.strftime("%Y-%m-%d")}: ${amount}' for user_id in group_amounts[group_id] for date, amount in group_amounts[group_id][user_id])
                reply_msg = f'總金額: ${total_amount}\n記錄:\n{records}'
            else:
                reply_msg = '目前沒有記錄任何金額'
        else:
            reply_msg = '請輸入有效指令，如「記錄金額 yyyy.mm.dd $金額」或「查詢總金額」'

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
