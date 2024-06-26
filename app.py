import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextMessage, TextSendMessage, MessageEvent
import dropbox
import json
from datetime import datetime

app = Flask(__name__)

# Line Bot 相关配置
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))

# Dropbox 访问令牌配置
DROPBOX_ACCESS_TOKEN = os.getenv('DROPBOX_ACCESS_TOKEN')
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# 记录群组金额与待开发票
group_amounts = {}

# 检查是否有存储的金额记录文件，若有则加载
def load_group_amounts():
    try:
        _, res = dbx.files_download("/group_amounts.json")
        return json.loads(res.content)
    except Exception as e:
        print(f"Error loading group amounts from Dropbox: {e}")
        return {}

def save_group_amounts():
    try:
        with open("group_amounts.json", "w") as f:
            json.dump(group_amounts, f, ensure_ascii=False, indent=4)
        with open("group_amounts.json", "rb") as f:
            dbx.files_upload(f.read(), "/group_amounts.json", mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        print(f"Error saving group amounts to Dropbox: {e}")

# 载入群组金额记录
group_amounts = load_group_amounts()

# 检查访问令牌是否有效
def is_token_valid():
    try:
        # 进行一次简单的 Dropbox API 调用来检查访问令牌是否仍然有效
        account_info = dbx.users_get_current_account()
        return True
    except dropbox.exceptions.AuthError:
        return False

# 刷新访问令牌
def refresh_access_token():
    global DROPBOX_ACCESS_TOKEN, dbx
    
    try:
        # 使用 refresh_token 刷新访问令牌
        refresh_token = os.getenv('DROPBOX_REFRESH_TOKEN')
        oauth2_refresh_token = dropbox.oauth2.RefreshAccessToken(refresh_token)
        DROPBOX_ACCESS_TOKEN = oauth2_refresh_token.refresh_token
        dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
        
        print(f"已更新存取令牌：{DROPBOX_ACCESS_TOKEN}")
        
        # 在更新访问令牌后，保存新的访问令牌
        # 请确保将新的访问令牌存储在安全的地方，例如环境变量或数据库
        os.environ['DROPBOX_ACCESS_TOKEN'] = DROPBOX_ACCESS_TOKEN
        
    except Exception as e:
        print(f"更新存取令牌时出错：{e}")

# 每次启动应用程序时检查访问令牌是否有效，若无效则刷新
if not is_token_valid():
    refresh_access_token()

# 处理 Line Bot 的 Webhook 请求
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

# 简单的根路径返回 Hello World
@app.route("/", methods=['GET'])
def index():
    return 'Hello World! This is a LINE Bot.'

# 处理用户发来的消息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global group_amounts
    
    msg = event.message.text
    user_id = event.source.user_id
    group_id = event.source.group_id
    
    try:
        if msg == '指令':
            reply_msg = '请发送有效指令，如「记录金额 yyyy.mm.dd $金额」、「记录汇款 yyyy.mm.dd $金额」、「记录待开发票 $金额 厂商名字」、「查询总金额」、「删除金额 yyyy.mm.dd」、「删除汇款 yyyy.mm.dd」或「删除待开发票 $金额 厂商名字」'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
        elif msg.startswith('记录金额 '):
            lines = msg.splitlines()
            success_msgs = []
            error_msgs = []
            for line in lines:
                parts = line.split(' ')
                if len(parts) == 3:
                    date_str = parts[1]
                    amount_str = parts[2].replace('$', '').replace('＄', '').strip()
                    if amount_str.replace('.', '', 1).isdigit():  # 检查是否为有效的金额格式
                        amount = float(amount_str)
                        date = datetime.strptime(date_str, '%Y.%m.%d').date()
                        if group_id not in group_amounts:
                            group_amounts[group_id] = {'unpaid': {}, 'paid': {}, 'invoices': {}}
                        if user_id not in group_amounts[group_id]['unpaid']:
                            group_amounts[group_id]['unpaid'][user_id] = []
                        group_amounts[group_id]['unpaid'][user_id].append((date_str, amount))
                        success_msgs.append(f'已记录 {date_str} 的货款 {amount}')
                    else:
                        error_msgs.append(f'金额格式错误: {amount_str}')
                else:
                    error_msgs.append(f'指令格式错误: {line}')
            
            if success_msgs:
                save_group_amounts()
                unpaid_total = sum(amount for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                unpaid_records = '\n'.join(f'{date_str}: ${amount}' for user_id in group_amounts[group_id]['unpaid'] for date_str, amount in group_amounts[group_id]['unpaid'][user_id])
                reply_msg = '\n'.join(success_msgs) + f'\n\n----- 当前待付款总额: ${unpaid_total}\n待付款记录:\n{unpaid_records}'
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
	
