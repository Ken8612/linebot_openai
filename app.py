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

# 記錄群組的金額與待開發票
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
        if msg == '指令':
            reply_msg = '請輸入有效指令，如「記錄金額 yyyy.mm.dd $金額」、「記錄匯款 yyyy.mm.dd $金額」、「記錄待開發票 $金額 廠商名字」、「查詢總金額」、「刪除金額 yyyy.mm.dd」、「刪除匯款 yyyy.mm.dd」或「刪除待開發票 $金額 廠商名字」'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
        elif msg.startswith('記錄金額 '):
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
                        if group_id not in group_amounts:
                            group_amounts[group_id] = {'unpaid': {}, 'paid': {}, 'invoices': {}}
                        if user_id not in group_amounts[group_id]['unpaid']:
                            group_amounts[group_id]['unpaid'][user_id] = []
                        group_amounts[group_id]['unpaid'][user_id].append((date_str, amount))
                        success_msgs.append(f'已記錄 {date_str} 的貨款 {amount}')
                    else:
                        error_msgs.append(f'金額格式錯誤: {amount_str}')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                unpaid_total = sum(amount for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                unpaid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前待付款總額: ${unpaid_total}\n待付款記錄:\n{unpaid_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg.startswith('記錄匯款 '):
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
                        if group_id not in group_amounts:
                            group_amounts[group_id] = {'unpaid': {}, 'paid': {}, 'invoices': {}}
                        if user_id not in group_amounts[group_id]['paid']:
                            group_amounts[group_id]['paid'][user_id] = []
                        group_amounts[group_id]['paid'][user_id].append((date_str, amount))
                        success_msgs.append(f'已記錄 {date_str} 的匯款 {amount}')
                    else:
                        error_msgs.append(f'金額格式錯誤: {amount_str}')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                paid_total = sum(amount for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                paid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前已匯款總額: ${paid_total}\n已匯款記錄:\n{paid_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg.startswith('記錄待開發票 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 4:
                    amount_str = parts[1].replace('$', '').replace('＄', '').strip()
                    supplier_name = parts[3]
                    if amount_str.replace('.', '', 1).isdigit():  # 檢查是否為有效的金額格式
                        amount = float(amount_str)
                        if group_id not in group_amounts:
                            group_amounts[group_id] = {'unpaid': {}, 'paid': {}, 'invoices': {}}
                        if user_id not in group_amounts[group_id]['invoices']:
                            group_amounts[group_id]['invoices'][user_id] = []
                        group_amounts[group_id]['invoices'][user_id].append((amount, supplier_name))
                        success_msgs.append(f'已記錄待開發票金額 {amount} 廠商: {supplier_name}')
                    else:
                        error_msgs.append(f'金額格式錯誤: {amount_str}')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                invoice_total = sum(amount for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                invoice_records = '\n'.join(f'${amount} 廠商: {supplier}' for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前待開發票總額: ${invoice_total}\n待開發票記錄:\n{invoice_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg == '查詢總金額':
            if group_id in group_amounts:
                unpaid_total = sum(amount for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                paid_total = sum(amount for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                invoice_total = sum(amount for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                
                unpaid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                paid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                invoice_records = '\n'.join(f'${amount} 廠商: {supplier}' for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                
                reply_msg = (
                    f'待付款總額: ${unpaid_total}\n待付款記錄:\n{unpaid_records}\n\n'
                    f'已匯款總額: ${paid_total}\n已匯款記錄:\n{paid_records}\n\n'
                    f'待開發票總額: ${invoice_total}\n待開發票記錄:\n{invoice_records}'
                )
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
                    if group_id in group_amounts and user_id in group_amounts[group_id]['unpaid']:
                        group_amounts[group_id]['unpaid'][user_id] = [(d, a) for d, a in group_amounts[group_id]['unpaid'][user_id] if d != date_str]
                        success_msgs.append(f'已刪除 {date_str} 的所有待付款記錄')
                    else:
                        error_msgs.append(f'找不到 {date_str} 的待付款記錄')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                unpaid_total = sum(amount for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                unpaid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前待付款總額: ${unpaid_total}\n待付款記錄:\n{unpaid_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg.startswith('刪除匯款 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 2:
                    date_str = parts[1]
                    if group_id in group_amounts and user_id in group_amounts[group_id]['paid']:
                        group_amounts[group_id]['paid'][user_id] = [(d, a) for d, a in group_amounts[group_id]['paid'][user_id] if d != date_str]
                        success_msgs.append(f'已刪除 {date_str} 的所有匯款記錄')
                    else:
                        error_msgs.append(f'找不到 {date_str} 的匯款記錄')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                paid_total = sum(amount for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                paid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['paid'] for date_str, amount in group_amounts[group_id]['paid'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前已匯款總額: ${paid_total}\n已匯款記錄:\n{paid_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        elif msg.startswith('刪除待開發票 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 4:
                    amount_str = parts[1].replace('$', '').replace('＄', '').strip()
                    supplier_name = parts[3]
                    if amount_str.replace('.', '', 1).isdigit():  # 檢查是否為有效的金額格式
                        amount = float(amount_str)
                        if group_id in group_amounts and user_id in group_amounts[group_id]['invoices']:
                            group_amounts[group_id]['invoices'][user_id] = [(a, s) for a, s in group_amounts[group_id]['invoices'][user_id] if not (a == amount and s == supplier_name)]
                            success_msgs.append(f'已刪除待開發票金額 {amount} 廠商: {supplier_name}')
                        else:
                            error_msgs.append(f'找不到待開發票金額 {amount} 廠商: {supplier_name} 的記錄')
                    else:
                        error_msgs.append(f'金額格式錯誤: {amount_str}')
                else:
                    error_msgs.append(f'指令格式錯誤: {line}')
            
            if success_msgs:
                save_group_amounts()  # 儲存更新後的金額記錄
                invoice_total = sum(amount for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                invoice_records = '\n'.join(f'${amount} 廠商: {supplier}' for user_id in group_amounts[group_id]['invoices'] for amount, supplier in group_amounts[group_id]['invoices'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 目前待開發票總額: ${invoice_total}\n待開發票記錄:\n{invoice_records}'
            else:
                reply_msg = '\n'.join(error_msgs)
        
        # 如果收到一般文字訊息，不回覆任何訊息
        else:
            return
    
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
    except Exception as e:
        print(traceback.format_exc())
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='發生錯誤，請稍後再試'))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
