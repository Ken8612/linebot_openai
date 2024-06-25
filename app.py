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

# Dictionary to store user-specific amounts
user_amounts = {}

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

   if msg.startswith('記錄金額 '):
    try:
        parts = msg.split(' ')
        if len(parts) == 3:
            date_str = parts[1]
            amount_str = parts[2].replace('$', '').replace('＄', '').strip()
            if amount_str.isdigit() or (amount_str[0] == '-' and amount_str[1:].isdigit()):
                amount = float(amount_str)
                date = datetime.strptime(date_str, '%y.%m.%d').date()
                if user_id in user_amounts:
                    user_amounts[user_id].append((date, amount))
                else:
                    user_amounts[user_id] = [(date, amount)]
                reply_msg = f'已記錄 {date_str} 的金額 {amount}'
            else:
                reply_msg = '金額格式錯誤，請輸入有效的數字'
        else:
            reply_msg = '指令格式錯誤，請使用「記錄金額 yy.mm.dd $金額」的格式'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
    except ValueError:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='金額格式錯誤，請輸入有效的數字'))
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

    
    elif msg == '查詢總金額':
        if user_id in user_amounts and len(user_amounts[user_id]) > 0:
            total_amount = sum(amount for _, amount in user_amounts[user_id])
            record_msg = '\n'.join(f'{date.strftime("%y.%m.%d")}: ${amount}' for date, amount in user_amounts[user_id])
            reply_msg = f'您目前的總金額為 {total_amount}\n\n記錄如下:\n{record_msg}'
        else:
            reply_msg = '您尚未有任何記錄的金額'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
    
    else:
        try:
            # 簡單地將使用者的訊息原樣回覆
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        except Exception as e:
            print(traceback.format_exc())
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
