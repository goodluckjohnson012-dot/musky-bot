
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import threading
import os
import uuid
import html
import re
import random
import copy
from datetime import datetime

# ============================================
# --- COPY BUTTON PATCH ---
# ============================================
_old_inline_dict = InlineKeyboardButton.to_dict
def _new_inline_dict(self):
    d = _old_inline_dict(self)
    if hasattr(self, 'custom_copy_text') and self.custom_copy_text:
        d['copy_text'] = {'text': str(self.custom_copy_text)}
        if 'callback_data' in d:
            del d['callback_data']
    return d
InlineKeyboardButton.to_dict = _new_inline_dict

# ============================================
# --- CONFIGURATION ---
# ============================================
TOKEN = "8161221675:AAHMmjJ_x_jH9_22lw_YNychUhIsDwtia0c"
ADMIN_ID = 8017839068
GROUP_ID = -1003793881191

# API Configuration - BOTH APIs PRE-CONFIGURED
MBC_API = {
    "url": "https://mbcs-ms.com/crapi/mbc/viewstats",
    "token": "Gb_h93NzQahJGr2o13LgnM9XHnfk4Arv3RY8RYFGejA",
}

REZ_API = {
    "url": "http://166.1.2.54/api/cdr.php",
    "token": "b2facd0bab797cf70b989c27f0947a01800ee5aff2d1c2a3fff75a8253658971",
}

# ============================================
# --- BOT INITIALIZATION ---
# ============================================
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

req_session = requests.Session()
retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(pool_connections=1000, pool_maxsize=1000, max_retries=retries)
req_session.mount('http://', adapter)
req_session.mount('https://', adapter)

DATA_FILE = "musky_bot_data.json"
user_states = {}
data_lock = threading.RLock()
menu_message_id = {}
user_cooldowns = {}
active_requests = {}
forwarded_otp_ids = set()
sent_old_otps = False

# ============================================
# --- DATA MANAGEMENT ---
# ============================================
def load_data():
    with data_lock:
        if not os.path.exists(DATA_FILE):
            default_data = {
                "users": [],
                "forward_groups": [GROUP_ID],
                "main_otp_link": "https://t.me/",
                "watermark": "Musky Tech",
                "otp_counts": {},
                "balances": {},
                "withdrawals": [],
                "numbers": {},
                "services": ["WhatsApp", "Facebook", "IMO", "PayPal", "Telegram", "Instagram"],
                "settings": {
                    "cooldown": 60,
                    "num_per_request": 5,
                    "support_link": "https://t.me/Goodyboy3",
                    "per_otp_amount": 0.005,
                    "min_withdrawal": 0.50
                },
                "extra_admins": [],
                "banned_users": [],
                "month_sms": 0,
                "today_sms": 0,
                "sms_date": "",
                "forwarded_otp_ids": []
            }
            with open(DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(default_data, f, indent=4)
            return default_data
        with open(DATA_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
            if "forwarded_otp_ids" not in data:
                data["forwarded_otp_ids"] = []
            if "numbers" not in data:
                data["numbers"] = {}
            if "services" not in data:
                data["services"] = ["WhatsApp", "Facebook", "IMO", "PayPal", "Telegram", "Instagram"]
            if "settings" not in data:
                data["settings"] = {
                    "cooldown": 60,
                    "num_per_request": 5,
                    "support_link": "https://t.me/Goodyboy3",
                    "per_otp_amount": 0.005,
                    "min_withdrawal": 0.50
                }
            if "balances" not in data:
                data["balances"] = {}
            if "withdrawals" not in data:
                data["withdrawals"] = []
            return data

def save_data(data):
    with data_lock:
        with open(DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4)

def add_user(user_id):
    data = load_data()
    if user_id not in data.get("users", []):
        data.setdefault("users", []).append(user_id)
        if str(user_id) not in data.get("balances", {}):
            data["balances"][str(user_id)] = 0.0
        save_data(data)

def add_balance(user_id, amount):
    data = load_data()
    user_id_str = str(user_id)
    if "balances" not in data:
        data["balances"] = {}
    if user_id_str not in data["balances"]:
        data["balances"][user_id_str] = 0.0
    data["balances"][user_id_str] = round(data["balances"][user_id_str] + amount, 8)
    save_data(data)
    return data["balances"][user_id_str]

def get_balance(user_id):
    data = load_data()
    return data.get("balances", {}).get(str(user_id), 0.0)

# ============================================
# --- HELPER FUNCTIONS ---
# ============================================
def clean_html_tags(text):
    text = re.sub(r'<tg-emoji[^>]*>', '', text)
    text = re.sub(r'</tg-emoji>', '', text)
    return text

def delete_after_delay(chat_id, message_id, delay):
    """Delete a message after a delay"""
    time.sleep(delay)
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def safe_send(chat_id, text, reply_markup=None, reply_to=None):
    clean_text = clean_html_tags(text)
    try:
        msg = bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup, reply_to_message_id=reply_to)
        return msg
    except:
        return None

def safe_edit(chat_id, text, reply_markup=None, message_id=None):
    clean_text = clean_html_tags(text)
    
    try:
        if chat_id in menu_message_id and menu_message_id[chat_id] != message_id:
            bot.delete_message(chat_id, menu_message_id[chat_id])
    except:
        pass
    
    target_msg_id = message_id if message_id else menu_message_id.get(chat_id)
    if target_msg_id:
        try:
            msg = bot.edit_message_text(clean_text, chat_id=chat_id, message_id=target_msg_id, parse_mode="HTML", reply_markup=reply_markup)
            if msg:
                menu_message_id[chat_id] = msg.message_id
            return msg
        except:
            pass
    
    try:
        msg = bot.send_message(chat_id, clean_text, parse_mode="HTML", reply_markup=reply_markup)
        if msg:
            menu_message_id[chat_id] = msg.message_id
        return msg
    except:
        return None

def ibtn(text, callback_data=None, url=None, copy_text_str=None):
    kwargs = {'text': text}
    if copy_text_str:
        kwargs['callback_data'] = "fake_copy_btn"
        b = InlineKeyboardButton(**kwargs)
        b.custom_copy_text = copy_text_str
        return b
    if callback_data:
        kwargs['callback_data'] = callback_data
    if url:
        kwargs['url'] = url
    return InlineKeyboardButton(**kwargs)

def rbtn(text):
    return KeyboardButton(text=text)

# ============================================
# --- STATUS INDICATORS ---
# ============================================
def get_status_emoji(status):
    status_map = {
        "active": "🟢",
        "inactive": "🔴",
        "pending": "🟡",
        "approved": "✅",
        "rejected": "❌",
        "waiting": "⏳",
        "received": "🔔",
        "available": "🟢",
        "used": "🔴",
        "success": "✅",
        "failed": "❌",
        "delivered": "📨",
        "processing": "🔄",
        "timeout": "⏰",
    }
    return status_map.get(str(status).lower(), "⚪")

def get_service_color(service):
    colors = {
        "whatsapp": "💚", "facebook": "📘", "imo": "💭", "paypal": "💵",
        "telegram": "✈️", "instagram": "📷", "google": "🔍", "gmail": "📧",
        "youtube": "🎬", "apple": "🍎", "microsoft": "💻", "tiktok": "🎵",
        "snapchat": "👻", "twitter": "𝕏", "binance": "💰", "melbet": "🎰",
        "1xbet": "🎰", "22bet": "🎰", "lucky pari": "🍀", "bkash": "💳",
        "nagad": "📲", "bolt": "⚡", "uber": "🚗", "amazon": "📦",
        "netflix": "🎬", "discord": "💬", "spotify": "🎧", "linkedin": "💼",
        "yahoo": "📧", "viber": "💜", "line": "💚", "wechat": "💚", "signal": "🔒"
    }
    name = str(service).lower().strip()
    for key, color in colors.items():
        if key in name or name in key:
            return color
    return "✨"

def get_country_color(country):
    country_colors = {
        "yemen": "🇾🇪", "iran": "🇮🇷", "benin": "🇧🇯", "guinea": "🇬🇳",
        "venezuela": "🇻🇪", "nigeria": "🇳🇬", "usa": "🇺🇸", "uk": "🇬🇧",
        "india": "🇮🇳", "pakistan": "🇵🇰", "bangladesh": "🇧🇩", "uae": "🇦🇪",
        "saudi arabia": "🇸🇦", "egypt": "🇪🇬", "turkey": "🇹🇷", "russia": "🇷🇺",
        "china": "🇨🇳", "japan": "🇯🇵", "south korea": "🇰🇷", "brazil": "🇧🇷",
        "argentina": "🇦🇷", "mexico": "🇲🇽", "canada": "🇨🇦", "australia": "🇦🇺",
        "france": "🇫🇷", "germany": "🇩🇪", "italy": "🇮🇹", "spain": "🇪🇸",
        "portugal": "🇵🇹", "netherlands": "🇳🇱", "belgium": "🇧🇪", "switzerland": "🇨🇭",
        "ghana": "🇬🇭", "kenya": "🇰🇪", "tanzania": "🇹🇿", "uganda": "🇺🇬",
        "rwanda": "🇷🇼", "zimbabwe": "🇿🇼"
    }
    name = str(country).lower().strip()
    for key, color in country_colors.items():
        if key in name or name in key:
            return color
    return "🌍"

# ============================================
# --- FLAG & COUNTRY FUNCTIONS ---
# ============================================
def get_country_flag(country_name):
    flags = {
        "yemen": "🇾🇪", "iran": "🇮🇷", "benin": "🇧🇯", "guinea": "🇬🇳",
        "venezuela": "🇻🇪", "nigeria": "🇳🇬", "usa": "🇺🇸", "uk": "🇬🇧",
        "india": "🇮🇳", "pakistan": "🇵🇰", "bangladesh": "🇧🇩",
        "uae": "🇦🇪", "saudi arabia": "🇸🇦", "egypt": "🇪🇬",
        "turkey": "🇹🇷", "russia": "🇷🇺", "china": "🇨🇳",
        "japan": "🇯🇵", "south korea": "🇰🇷", "brazil": "🇧🇷",
        "argentina": "🇦🇷", "mexico": "🇲🇽", "canada": "🇨🇦",
        "australia": "🇦🇺", "france": "🇫🇷", "germany": "🇩🇪",
        "italy": "🇮🇹", "spain": "🇪🇸", "portugal": "🇵🇹",
        "netherlands": "🇳🇱", "belgium": "🇧🇪", "switzerland": "🇨🇭",
        "mozambique": "🇲🇿", "angola": "🇦🇴", "south africa": "🇿🇦",
        "ghana": "🇬🇭", "kenya": "🇰🇪", "tanzania": "🇹🇿",
        "uganda": "🇺🇬", "rwanda": "🇷🇼", "zimbabwe": "🇿🇼"
    }
    name = str(country_name).lower().strip()
    for key, flag in flags.items():
        if key in name or name in key:
            return flag
    return "🌍"

def get_iso_code(country_name):
    iso_map = {
        "yemen": "YE", "iran": "IR", "benin": "BJ", "guinea": "GN",
        "venezuela": "VE", "nigeria": "NG", "usa": "US", "uk": "GB",
        "india": "IN", "pakistan": "PK", "bangladesh": "BD",
        "uae": "AE", "saudi arabia": "SA", "egypt": "EG",
        "turkey": "TR", "russia": "RU", "china": "CN",
        "japan": "JP", "south korea": "KR", "brazil": "BR",
        "argentina": "AR", "mexico": "MX", "canada": "CA",
        "australia": "AU", "france": "FR", "germany": "DE",
        "italy": "IT", "spain": "ES", "portugal": "PT",
        "netherlands": "NL", "belgium": "BE", "switzerland": "CH",
        "mozambique": "MZ", "angola": "AO", "south africa": "ZA",
        "ghana": "GH", "kenya": "KE", "tanzania": "TZ",
        "uganda": "UG", "rwanda": "RW", "zimbabwe": "ZW"
    }
    name = str(country_name).lower().strip()
    for key, iso in iso_map.items():
        if key in name or name in key:
            return iso
    return name[:2].upper() if len(name) >= 2 else "UN"

def emo(keyword):
    emojis = {
        "whatsapp": "💚", "facebook": "📘", "imo": "💭", "paypal": "💵",
        "telegram": "✈️", "instagram": "📷", "google": "🔍",
        "tiktok": "🎵", "snapchat": "👻", "twitter": "𝕏",
        "binance": "💰", "melbet": "🎰", "1xbet": "🎰", "22bet": "🎰",
        "lucky pari": "🍀", "bkash": "💳", "nagad": "📲",
        "bolt": "⚡", "uber": "🚗", "amazon": "📦",
        "netflix": "🎬", "discord": "💬", "spotify": "🎧",
        "linkedin": "💼", "yahoo": "📧", "viber": "💜",
        "line": "💚", "wechat": "💚", "signal": "🔒"
    }
    kw = str(keyword).lower().strip()
    for key, emoji in emojis.items():
        if key in kw or kw in key:
            return emoji
    return "✨"

def mask_number(phone):
    phone_str = str(phone).replace('+', '')
    if len(phone_str) >= 6:
        return f"{phone_str[:3]}xx{phone_str[-3:]}"
    return phone_str

def get_country_from_number(phone_number):
    phone_map = {
        "967": "Yemen", "989": "Iran", "229": "Benin", "241": "Guinea",
        "58": "Venezuela", "234": "Nigeria", "1": "USA", "44": "UK",
        "91": "India", "92": "Pakistan", "880": "Bangladesh",
        "971": "UAE", "966": "Saudi Arabia", "20": "Egypt",
        "90": "Turkey", "7": "Russia", "86": "China",
        "81": "Japan", "82": "South Korea", "55": "Brazil",
        "54": "Argentina", "52": "Mexico", "1": "Canada",
        "61": "Australia", "33": "France", "49": "Germany",
        "39": "Italy", "34": "Spain", "351": "Portugal",
        "31": "Netherlands", "32": "Belgium", "41": "Switzerland",
        "258": "Mozambique", "244": "Angola", "27": "South Africa",
        "233": "Ghana", "254": "Kenya", "255": "Tanzania",
        "256": "Uganda", "250": "Rwanda", "263": "Zimbabwe"
    }
    number = str(phone_number).replace('+', '').strip()
    for code_len in [3, 2, 1]:
        if len(number) >= code_len:
            code = number[:code_len]
            if code in phone_map:
                return phone_map[code]
    return "Unknown"

def detect_service(text):
    if not text:
        return "Unknown"
    text_lower = str(text).lower()
    
    services = {
        "whatsapp": ["whatsapp", "wa", "whatsapp business", "whatsapp code"],
        "facebook": ["facebook", "fb", "facebook code", "fb code"],
        "imo": ["imo", "imo verification", "imo code"],
        "paypal": ["paypal", "pay pal", "security code", "paypal code"],
        "telegram": ["telegram", "tg", "telegram code"],
        "instagram": ["instagram", "insta", "ig", "instagram code"],
        "google": ["google", "gmail", "google code", "gmail code"],
        "binance": ["binance", "bnb", "binance code"],
        "melbet": ["melbet", "mel", "melbet code"],
        "1xbet": ["1xbet", "1x bet", "1xbet code"],
        "22bet": ["22bet", "22 bet", "22bet code"],
        "lucky pari": ["lucky pari", "luckypari", "lucky pari code"],
        "bkash": ["bkash", "b-kash", "bkash code"],
        "nagad": ["nagad", "nagad code"],
        "bolt": ["bolt", "bolt code", "bolt verification"],
        "uber": ["uber", "uber code", "uber verification"],
        "amazon": ["amazon", "amzn", "amazon code"],
        "netflix": ["netflix", "netflix code"],
        "discord": ["discord", "discord code"],
        "spotify": ["spotify", "spotify code"],
        "tiktok": ["tiktok", "tik tok", "tiktok code"],
        "snapchat": ["snapchat", "snap", "snapchat code"],
        "twitter": ["twitter", "x.com", "x code", "twitter code"],
        "linkedin": ["linkedin", "linked in", "linkedin code"],
        "yahoo": ["yahoo", "yahoo code"],
        "viber": ["viber", "viber code"],
        "line": ["line", "line code"],
        "wechat": ["wechat", "we chat", "wechat code"],
        "signal": ["signal", "signal code"],
        "apple": ["apple", "icloud", "apple id", "apple code"],
        "microsoft": ["microsoft", "ms", "outlook", "microsoft code"]
    }
    
    for service, keywords in services.items():
        for kw in keywords:
            if kw in text_lower:
                return service.title()
    
    match = re.search(r'(?:your|for|to)\s+([a-zA-Z]+)\s+(?:code|account|verification)', text_lower)
    if match:
        return match.group(1).title()
    
    return "Unknown"

def extract_otp(text):
    if not text:
        return None
    patterns = [
        r'(?:code|otp|security code|security_code|Your.*code|is)\D{0,10}(\d{4,8})',
        r'(?:<#>\s*)?(\d{4,8})',
        r'(\d{3,6}[- ]\d{3,6})',
        r'#\s*(\d{4,8})',
        r'security code is (\d{4,8})',
        r'code (\d{4,8})'
    ]
    for pattern in patterns:
        match = re.search(pattern, str(text), re.IGNORECASE)
        if match:
            return match.group(1).strip().replace('-', '').replace(' ', '')
    matches = re.findall(r'\b(\d{4,8})\b', str(text))
    if matches:
        return matches[0]
    return None

def detect_language(text):
    if not text:
        return "English"
    
    text_lower = str(text).lower()
    
    if any('\u0600' <= c <= '\u06ff' for c in text):
        if any(w in text_lower for w in ["كود", "رمز", "تحقق"]):
            return "Arabic"
        if any(w in text_lower for w in ["کوڈ", "رمز"]):
            return "Urdu"
        if any(w in text_lower for w in ["کد", "رمز"]):
            return "Persian"
        return "Arabic"
    
    if any('\u0400' <= c <= '\u04ff' for c in text):
        return "Russian"
    if any('\u0370' <= c <= '\u03ff' for c in text):
        return "Greek"
    if any('\u0590' <= c <= '\u05ff' for c in text):
        return "Hebrew"
    if any('\u0900' <= c <= '\u097f' for c in text):
        return "Hindi"
    if any('\u0980' <= c <= '\u09ff' for c in text):
        return "Bengali"
    if any('\u0b80' <= c <= '\u0bff' for c in text):
        return "Tamil"
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        return "Chinese"
    if any('\u3040' <= c <= '\u30ff' for c in text):
        return "Japanese"
    if any('\uac00' <= c <= '\ud7af' for c in text):
        return "Korean"
    
    if any(w in text_lower for w in ["code", "verification", "password"]):
        return "English"
    if any(w in text_lower for w in ["código", "verificación", "contraseña"]):
        return "Spanish"
    if any(w in text_lower for w in ["code", "vérification", "mot de passe"]):
        return "French"
    if any(w in text_lower for w in ["código", "senha", "verificação"]):
        return "Portuguese"
    if any(w in text_lower for w in ["doğrulama", "şifre", "kod"]):
        return "Turkish"
    if any(w in text_lower for w in ["kode", "verifikasi", "sandi"]):
        return "Indonesian"
    if any(w in text_lower for w in ["bestätigung", "sicherheitscode", "passwort"]):
        return "German"
    if any(w in text_lower for w in ["codice", "verifica", "password"]):
        return "Italian"
    if any(w in text_lower for w in ["verificatie", "bevestigingscode", "wachtwoord"]):
        return "Dutch"
    if any(w in text_lower for w in ["kod", "weryfikacyjny", "hasło"]):
        return "Polish"
    
    return "English"

def format_url(url):
    url = url.strip()
    if url and not url.startswith(('http://', 'https://', 'tg://')):
        return 'https://' + url
    return url

# ============================================
# --- API FUNCTIONS - BOTH APIs CONFIGURED ---
# ============================================
def fetch_mbc_otps():
    try:
        url = f"{MBC_API['url']}?token={MBC_API['token']}&records=50"
        response = req_session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data"):
                return data["data"]
        return []
    except Exception as e:
        print(f"MBC API error: {e}")
        return []

def fetch_rez_otps():
    try:
        now = datetime.now()
        dt1 = "2026-07-11 00:00:00"
        dt2 = now.strftime("%Y-%m-%d %H:%M:%S")
        url = f"{REZ_API['url']}?token={REZ_API['token']}&dt1={dt1}&dt2={dt2}&records=100"
        response = req_session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data"):
                return data["data"]
        return []
    except Exception as e:
        print(f"REZ API error: {e}")
        return []

def fetch_all_otps():
    otps = []
    
    # MBC API
    mbc_data = fetch_mbc_otps()
    for item in mbc_data:
        otp = extract_otp(item.get("message", ""))
        if otp:
            service = item.get("cli", "Unknown")
            if service and service != "Unknown":
                service = service.title()
            else:
                service = detect_service(item.get("message", ""))
            
            otps.append({
                "id": f"mbc_{item.get('num', '')}_{item.get('dt', '')}",
                "service": service,
                "number": item.get("num", ""),
                "message": item.get("message", ""),
                "otp": otp,
                "source": "MBC",
                "dt": item.get("dt", "")
            })
    
    # REZ API
    rez_data = fetch_rez_otps()
    for item in rez_data:
        otp = extract_otp(item.get("message", ""))
        if not otp:
            security_code = item.get("security_code", "")
            if security_code:
                otp_match = re.search(r'\d{4,8}', str(security_code))
                if otp_match:
                    otp = otp_match.group(0)
        
        if otp:
            service = item.get("cli", "Unknown")
            if service and service != "Unknown":
                service = service.title()
            else:
                service = detect_service(item.get("message", ""))
            
            number = item.get("number", "") or item.get("num", "")
            otps.append({
                "id": f"rez_{item.get('message_id', '')}_{item.get('date_time', '')}",
                "service": service,
                "number": number,
                "message": item.get("message", ""),
                "otp": otp,
                "source": "REZ",
                "dt": item.get("date_time", "")
            })
    
    return otps

def get_number_from_pool(service, country):
    data = load_data()
    numbers = data.get("numbers", {})
    
    if service not in numbers:
        return None
    if country not in numbers[service]:
        return None
    
    available = [n for n in numbers[service][country] if not n.get("used", False)]
    if not available:
        return None
    
    chosen = random.choice(available)
    chosen["used"] = True
    save_data(data)
    return chosen["number"]

def release_number(service, country, number):
    data = load_data()
    numbers = data.get("numbers", {})
    
    if service in numbers and country in numbers[service]:
        for n in numbers[service][country]:
            if n["number"] == number:
                n["used"] = False
                save_data(data)
                return True
    return False

def get_total_stock(service, country):
    data = load_data()
    numbers = data.get("numbers", {})
    
    if service not in numbers:
        return 0
    if country not in numbers[service]:
        return 0
    
    available = [n for n in numbers[service][country] if not n.get("used", False)]
    return len(available)

# ============================================
# --- SEND OTP FUNCTIONS ---
# ============================================
def send_otp_to_group(service, number, otp, country, full_sms="", language="English", dt=""):
    """Send OTP to group - Auto formatted and cleaned message"""
    try:
        flag = get_country_flag(country)
        full_number = number.replace('+', '') if number else ""
        
        clean_sms = full_sms.strip() if full_sms else ""
        if clean_sms:
            clean_sms = re.sub(r'@', '', clean_sms)
            clean_sms = clean_sms.replace('\\n', '\n')
            clean_sms = clean_sms.replace('n', '\n') if 'n' in clean_sms and '\n' not in clean_sms else clean_sms
            clean_sms = re.sub(r'\s+', ' ', clean_sms)
            
            sentences = re.split(r'(\.\s*|\n)', clean_sms)
            clean_sms = ''
            for i, part in enumerate(sentences):
                if i % 2 == 0 and part:
                    part = part[0].upper() + part[1:] if part else part
                clean_sms += part
            
            clean_sms = re.sub(r'code\s+code', 'code', clean_sms, flags=re.IGNORECASE)
            
            if len(clean_sms) > 500:
                clean_sms = clean_sms[:500] + "..."
        
        if not clean_sms or "failed" in clean_sms.lower():
            clean_sms = f"Sorry Mr musky I couldn't detect otp for this number {full_number}"
        
        text = (
            f"<b>{country} {service} OTP Received!</b>\n\n"
            f"⏰ <b>Time:</b> {dt if dt else datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST\n"
            f"🌍 <b>Country:</b> {country} {flag}\n"
            f"🛒 <b>Service:</b> {service}\n"
            f"📱 <b>Number:</b> {full_number}\n"
            f"🔑 <b>OTP:</b> <code>{otp}</code>\n"
        )
        
        text += f"\n💬 <b>Full Message:</b>\n{clean_sms}"
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            ibtn("📞 Get Number", url="https://t.me/jero_x_otp_bot"),
            ibtn("💥 Method Channel", url="https://t.me/Hexanumberchannel")
        )
        markup.add(ibtn("👨‍💻 DEV", url="https://t.me/Goodyboy3"))
        
        safe_send(GROUP_ID, text, markup)
        return True
    except Exception as e:
        print(f"Error sending to group: {e}")
        return False

def send_otp_to_user(chat_id, service, number, otp, country, amount, language="English"):
    """Send OTP to user - Without +"""
    try:
        flag = get_country_flag(country)
        full_number = number.replace('+', '') if number else ""
        balance = get_balance(chat_id)
        data = load_data()
        watermark = data.get("watermark", "Musky Tech")
        service_color = get_service_color(service)
        
        text = (
            f"🔔 New OTP Received!\n"
            f"{flag} {country} | {service_color} {service} | {full_number}\n"
            f"🔑 OTP: {otp}\n"
            f"💰 +${amount:.6f} Added | Balance: ${balance:.6f}\n\n"
            f"Powered By {watermark}"
        )
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(ibtn(f"📋 Copy Number: {full_number}", copy_text_str=full_number))
        markup.add(ibtn(f"📋 Copy OTP: {otp}", copy_text_str=otp))
        markup.add(ibtn("💳 Check Balance", callback_data="check_balance"))
        
        safe_send(chat_id, text, markup)
        return True
    except Exception as e:
        print(f"Error sending to user: {e}")
        return False

# ============================================
# --- OTP PROCESSING ---
# ============================================
def process_otps():
    global sent_old_otps
    
    data = load_data()
    forwarded_ids = set(data.get("forwarded_otp_ids", []))
    
    if not sent_old_otps:
        print("📤 Sending old OTPs from BOTH APIs to group...")
        all_otps = fetch_all_otps()
        old_count = 0
        for otp_data in all_otps:
            otp_id = otp_data["id"]
            if otp_id not in forwarded_ids:
                country = get_country_from_number(otp_data["number"])
                language = detect_language(otp_data.get("message", ""))
                dt = otp_data.get("dt", "")
                if send_otp_to_group(
                    otp_data["service"],
                    otp_data["number"],
                    otp_data["otp"],
                    country,
                    otp_data.get("message", ""),
                    language,
                    dt
                ):
                    forwarded_ids.add(otp_id)
                    old_count += 1
                    time.sleep(0.3)
        if old_count > 0:
            safe_send(GROUP_ID, f"✅ {old_count} old OTPs forwarded to group from BOTH APIs!")
        sent_old_otps = True
        data["forwarded_otp_ids"] = list(forwarded_ids)
        save_data(data)
        print("✅ Old OTPs sent. Now monitoring BOTH APIs for new ones...")
    
    current_otps = fetch_all_otps()
    for otp_data in current_otps:
        otp_id = otp_data["id"]
        if otp_id not in forwarded_ids:
            number = otp_data["number"]
            service = detect_service(otp_data["message"]) or otp_data["service"]
            otp = otp_data["otp"]
            country = get_country_from_number(number)
            language = detect_language(otp_data.get("message", ""))
            dt = otp_data.get("dt", "")
            data = load_data()
            per_otp = data.get("settings", {}).get("per_otp_amount", 0.005)
            
            send_otp_to_group(service, number, otp, country, otp_data.get("message", ""), language, dt)
            
            for chat_id_str, request_data in list(active_requests.items()):
                numbers = request_data.get("numbers", [])
                if number in numbers:
                    chat_id = int(chat_id_str)
                    add_balance(chat_id, per_otp)
                    send_otp_to_user(chat_id, service, number, otp, country, per_otp, language)
                    if number in numbers:
                        numbers.remove(number)
                    if not numbers:
                        active_requests.pop(chat_id_str, None)
                    else:
                        active_requests[chat_id_str]["numbers"] = numbers
                    break
            
            forwarded_ids.add(otp_id)
            data["forwarded_otp_ids"] = list(forwarded_ids)
            save_data(data)
            print(f"✅ Forwarded new OTP: {service} - {otp} (from {otp_data['source']})")

# ============================================
# --- TIMEOUT CHECKER ---
# ============================================
def check_timeout_requests():
    """Check for expired OTP requests (5 seconds timeout)"""
    while True:
        try:
            current_time = time.time()
            expired = []
            
            for chat_id_str, request_data in active_requests.items():
                if request_data.get("timestamp", 0) + 5 < current_time:
                    expired.append(chat_id_str)
            
            for chat_id_str in expired:
                chat_id = int(chat_id_str)
                request_data = active_requests.pop(chat_id_str, {})
                numbers = request_data.get("numbers", [])
                service = request_data.get("service", "")
                country = request_data.get("country", "")
                
                for num in numbers:
                    release_number(service, country, num)
                
                safe_send(chat_id, f"❌ No OTP received for your numbers\n💡 Please try requesting a new number")
                print(f"⏰ Timeout: User {chat_id} - No OTP received")
            
            time.sleep(5)
        except Exception as e:
            print(f"Timeout checker error: {e}")
            time.sleep(5)

# ============================================
# --- BOT COMMANDS ---
# ============================================
def get_main_menu(user_id):
    data = load_data()
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(rbtn("📱 Get Number"), rbtn("💸 Withdraw"))
    markup.add(rbtn("💰 Balance"), rbtn("🛠 Support"))
    if user_id == ADMIN_ID or user_id in data.get("extra_admins", []):
        markup.add(rbtn("⚙️ Admin Panel"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or message.from_user.first_name
    
    add_user(user_id)
    
    data = load_data()
    watermark = data.get("watermark", "Musky Tech")
    per_otp = data.get("settings", {}).get("per_otp_amount", 0.005)
    
    text = (
        f"👋 Welcome @{username} to {watermark}\n"
        f"💰 Earn ${per_otp:.6f} for each OTP received!"
    )
    
    msg = safe_send(chat_id, text, get_main_menu(user_id))
    if msg:
        menu_message_id[chat_id] = msg.message_id

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.chat.type != 'private':
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    add_user(user_id)
    
    data = load_data()
    if user_id in data.get("banned_users", []):
        safe_send(chat_id, "🚫 You are banned!")
        return
    
    if text in ["📱 Get Number", "Get Number"]:
        show_services(chat_id)
    elif text in ["💸 Withdraw", "Withdraw"]:
        show_withdraw_menu(chat_id)
    elif text in ["💰 Balance", "Balance"]:
        show_balance(chat_id)
    elif text in ["🛠 Support", "Support"]:
        show_support(chat_id)
    elif text in ["⚙️ Admin Panel", "Admin Panel"]:
        if user_id == ADMIN_ID or user_id in data.get("extra_admins", []):
            show_admin_panel(chat_id)

# ============================================
# --- MENU FUNCTIONS ---
# ============================================
def show_services(chat_id):
    data = load_data()
    services = data.get("services", [])
    
    if not services:
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("❌ No Services Available", callback_data="close_menu"))
        safe_edit(chat_id, "No services added yet. Contact admin.", markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for service in services:
        service_emoji = emo(service)
        markup.add(ibtn(f"{service_emoji} {service}", callback_data=f"service_{service}"))
    markup.add(ibtn("❌ Cancel", callback_data="close_menu"))
    safe_edit(chat_id, "Select a service:", markup)

def show_countries(chat_id, service):
    data = load_data()
    numbers = data.get("numbers", {})
    countries = []
    
    if service in numbers:
        countries = list(numbers[service].keys())
    
    if not countries:
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("🔙 Back", callback_data="back_services"))
        safe_edit(chat_id, f"No numbers available for {service}.", markup)
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for country in sorted(countries):
        flag = get_country_flag(country)
        markup.add(ibtn(f"{flag} {country}", callback_data=f"country_{service}_{country}"))
    markup.add(ibtn("🔙 Back", callback_data="back_services"))
    safe_edit(chat_id, f"Select country for {service}:", markup)

def show_balance(chat_id):
    balance = get_balance(chat_id)
    text = f"💰 Your Balance: ${balance:.6f}"
    safe_edit(chat_id, text, get_main_menu(chat_id))

def show_withdraw_menu(chat_id):
    balance = get_balance(chat_id)
    data = load_data()
    min_withdraw = data.get("settings", {}).get("min_withdrawal", 0.50)
    
    text = (
        f"💳 Withdrawal\n"
        f"━━━━━━━━━━━━━\n"
        f"💰 Balance: ${balance:.6f}\n"
        f"📊 Min Withdrawal: ${min_withdraw}\n"
        f"━━━━━━━━━━━━━\n"
        f"Payment Methods:\n"
        f"• USDT\n"
        f"• Opay\n"
        f"• Palmpay\n"
        f"• Monipoint\n"
        f"• Momo\n"
        f"• PayPal"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("💳 Request Withdrawal", callback_data="request_withdraw"))
    markup.add(ibtn("📋 History", callback_data="withdraw_history"))
    markup.add(ibtn("🔙 Back", callback_data="close_menu"))
    
    safe_edit(chat_id, text, markup)

def show_support(chat_id):
    text = "🛠 Support\n━━━━━━━━━━━━━\nContact admin for help."
    markup = InlineKeyboardMarkup()
    markup.add(ibtn("📩 Contact Admin", url="https://t.me/Goodyboy3"))
    markup.add(ibtn("🔙 Back", callback_data="close_menu"))
    safe_edit(chat_id, text, markup)

def show_admin_panel(chat_id):
    try:
        if chat_id in menu_message_id:
            bot.delete_message(chat_id, menu_message_id[chat_id])
            del menu_message_id[chat_id]
    except:
        pass
    
    data = load_data()
    st = data.get("settings", {})
    services = data.get("services", [])
    numbers = data.get("numbers", {})
    
    total_numbers = 0
    for svc in numbers.values():
        for cnt in svc.values():
            total_numbers += len(cnt)
    
    text = (
        f"⚙️ Admin Panel\n"
        f"━━━━━━━━━━━━━\n"
        f"📊 Stats:\n"
        f"👥 Users: {len(data.get('users', []))}\n"
        f"📦 Services: {len(services)}\n"
        f"📱 Numbers: {total_numbers}\n"
        f"💰 Per OTP: ${st.get('per_otp_amount', 0.005)}\n"
        f"💳 Min Withdrawal: ${st.get('min_withdrawal', 0.50)}\n"
        f"⏳ Cooldown: {st.get('cooldown', 60)}s\n"
        f"━━━━━━━━━━━━━"
    )
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("📋 Manage Numbers", callback_data="admin_numbers"))
    markup.add(ibtn("📦 Manage Services", callback_data="admin_services"))
    markup.add(ibtn("💰 Set Per OTP", callback_data="admin_per_otp"))
    markup.add(ibtn("💳 Set Min Withdraw", callback_data="admin_min_withdraw"))
    markup.add(ibtn("⏳ Set Cooldown", callback_data="admin_cooldown"))
    markup.add(ibtn("📋 Withdrawals", callback_data="admin_withdrawals"))
    markup.add(ibtn("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(ibtn("🔙 Close", callback_data="close_menu"))
    
    msg = safe_send(chat_id, text, markup)
    if msg:
        menu_message_id[chat_id] = msg.message_id

# ============================================
# --- ADMIN SERVICE & NUMBER MANAGEMENT ---
# ============================================

def process_add_service(message):
    chat_id = message.chat.id
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    if message.text and message.text.lower() == '/cancel':
        show_manage_services(chat_id)
        return
    
    service = message.text.strip()
    
    if not service:
        msg = safe_send(chat_id, "❌ Invalid service name!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
        show_manage_services(chat_id)
        return
    
    data = load_data()
    if "services" not in data:
        data["services"] = []
    
    if service not in data["services"]:
        data["services"].append(service)
        save_data(data)
        msg = safe_send(chat_id, f"✅ Service '{service}' added!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    else:
        msg = safe_send(chat_id, f"⚠️ Service '{service}' already exists!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    
    time.sleep(1)
    show_manage_services(chat_id)

def process_remove_service(message):
    chat_id = message.chat.id
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    service = message.text.strip()
    
    if not service:
        msg = safe_send(chat_id, "❌ Invalid service name!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
        show_manage_services(chat_id)
        return
    
    data = load_data()
    services = data.get("services", [])
    
    if service not in services:
        msg = safe_send(chat_id, f"❌ Service '{service}' not found!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
        show_manage_services(chat_id)
        return
    
    services.remove(service)
    if service in data.get("numbers", {}):
        del data["numbers"][service]
    
    save_data(data)
    msg = safe_send(chat_id, f"✅ Service '{service}' removed!")
    if msg:
        threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    
    time.sleep(1)
    show_manage_services(chat_id)

def show_manage_services(chat_id, message_id=None):
    data = load_data()
    services = data.get("services", [])
    
    text = "📦 Manage Services\n━━━━━━━━━━━━━\n"
    
    if not services:
        text += "No services added."
    else:
        for i, service in enumerate(services, 1):
            text += f"{i}. {service}\n"
    
    text += "\n━━━━━━━━━━━━━\n"
    text += "✅ Add Service: Click button and type name\n"
    text += "❌ Remove Service: Click button and type name"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(ibtn("➕ Add Service", callback_data="add_service"))
    markup.add(ibtn("❌ Remove Service", callback_data="remove_service"))
    markup.add(ibtn("🔙 Back to Admin", callback_data="admin_back"))
    
    safe_edit(chat_id, text, markup, message_id)

def show_manage_numbers(chat_id, message_id=None):
    data = load_data()
    numbers = data.get("numbers", {})
    
    text = "📋 Manage Numbers\n━━━━━━━━━━━━━\n"
    
    if not numbers:
        text += "No numbers added yet."
    else:
        for service, countries in numbers.items():
            for country, num_list in countries.items():
                available = len([n for n in num_list if not n.get("used", False)])
                text += f"{service} | {country} | {len(num_list)} total | {available} available\n"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("➕ Add Numbers", callback_data="add_numbers"))
    markup.add(ibtn("🔙 Back to Admin", callback_data="admin_back"))
    
    safe_edit(chat_id, text, markup, message_id)

def show_add_numbers(chat_id, message_id=None):
    data = load_data()
    services = data.get("services", [])
    
    if not services:
        markup = InlineKeyboardMarkup()
        markup.add(ibtn("🔙 Back", callback_data="admin_numbers"))
        safe_edit(chat_id, "❌ No services added. Add services first.", markup, message_id)
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    for service in services:
        service_emoji = emo(service)
        markup.add(ibtn(f"{service_emoji} {service}", callback_data=f"addnum_service_{service}"))
    markup.add(ibtn("🔙 Back", callback_data="admin_numbers"))
    
    safe_edit(chat_id, "Select service to add numbers:", markup, message_id)

def show_add_numbers_country(chat_id, service, message_id=None):
    safe_edit(chat_id, f"📝 Type the country name for {service}:\n\nExample: Yemen, Iran, USA, UK, etc.", None, message_id)
    bot.register_next_step_handler_by_chat_id(chat_id, process_add_country, service, message_id)

def process_add_country(message, service, msg_id):
    chat_id = message.chat.id
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    country = message.text.strip()
    
    if not country:
        msg = safe_send(chat_id, "❌ Invalid country name!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
        show_add_numbers(chat_id, msg_id)
        return
    
    safe_edit(chat_id, f"Send numbers for {service} - {country}\nOne per line or comma separated:", None, msg_id)
    bot.register_next_step_handler_by_chat_id(chat_id, process_add_numbers, service, country, msg_id)

def process_add_numbers(message, service, country, msg_id):
    chat_id = message.chat.id
    
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    if message.text and message.text.lower() == '/cancel':
        show_manage_numbers(chat_id, msg_id)
        return
    
    numbers_text = message.text.strip()
    numbers = []
    
    for line in numbers_text.split('\n'):
        for num in line.split(','):
            cleaned = re.sub(r'[^0-9]', '', num.strip())
            if len(cleaned) >= 7:
                numbers.append(cleaned)
    
    if numbers:
        data = load_data()
        if service not in data["numbers"]:
            data["numbers"][service] = {}
        if country not in data["numbers"][service]:
            data["numbers"][service][country] = []
        
        existing = [n["number"] for n in data["numbers"][service][country]]
        added = 0
        for num in numbers:
            if num not in existing:
                data["numbers"][service][country].append({"number": num, "used": False})
                added += 1
        
        save_data(data)
        
        msg = safe_send(chat_id, f"✅ Added {added} numbers for {service} - {country}")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    else:
        msg = safe_send(chat_id, "❌ No valid numbers found!")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    
    time.sleep(1)
    show_manage_numbers(chat_id, msg_id)

# ============================================
# --- REQUEST NUMBER ---
# ============================================
def request_number(chat_id, service, country):
    data = load_data()
    st = data.get("settings", {})
    
    cooldown = st.get("cooldown", 60)
    last_req = user_cooldowns.get(chat_id, 0)
    elapsed = time.time() - last_req
    if elapsed < cooldown:
        remaining = int(cooldown - elapsed)
        safe_edit(chat_id, f"⏳ Please wait {remaining}s before next request.", None, menu_message_id.get(chat_id))
        return
    
    numbers = []
    for _ in range(3):
        num = get_number_from_pool(service, country)
        if num:
            numbers.append(num)
    
    if not numbers:
        safe_edit(chat_id, f"❌ No numbers available for {service} - {country}. Please try again later.", None, menu_message_id.get(chat_id))
        return
    
    active_requests[str(chat_id)] = {
        "numbers": numbers,
        "service": service,
        "country": country,
        "timestamp": time.time()
    }
    user_cooldowns[chat_id] = time.time()
    
    flag = get_country_flag(country)
    service_color = get_service_color(service)
    total_stock = get_total_stock(service, country)
    
    text = f"{flag} {country} ({service_color} {service}) - {len(numbers)} Numbers Assigned:\n\n"
    
    markup = InlineKeyboardMarkup(row_width=1)
    for num in numbers:
        full_num = num.replace('+', '') if num else ""
        text += f"• {full_num}\n"
        markup.add(ibtn(f"📋 Copy {full_num}", copy_text_str=full_num))
    
    if total_stock > 100:
        stock_color = "🟢"
    elif total_stock > 20:
        stock_color = "🟡"
    else:
        stock_color = "🔴"
    
    text += f"\n{stock_color} Stock Left: {total_stock}\n⏳ Waiting for OTP..."
    
    markup.add(ibtn("🔄 Change Numbers", callback_data=f"change_numbers_{service}_{country}"))
    markup.add(ibtn("🌍 Change Country", callback_data=f"change_country_{service}"))
    markup.add(ibtn("📦 Change Service", callback_data="back_services"))
    markup.add(ibtn("👁️ View OTP", url="https://t.me/otpgroup56"))
    markup.add(ibtn("🔙 Back", callback_data="close_menu"))
    
    safe_edit(chat_id, text, markup, menu_message_id.get(chat_id))
    print(f"User {chat_id} requested {service} - {country} with numbers: {numbers}")

# ============================================
# --- WITHDRAWAL FUNCTIONS ---
# ============================================
def request_withdrawal(chat_id):
    balance = get_balance(chat_id)
    data = load_data()
    min_withdraw = data.get("settings", {}).get("min_withdrawal", 0.50)
    
    if balance < min_withdraw:
        safe_edit(chat_id, f"❌ Insufficient balance!\n💰 Balance: ${balance:.6f}\n💳 Min Withdrawal: ${min_withdraw}")
        return
    
    safe_edit(chat_id, "💳 Enter withdrawal amount (or 'all' for full balance):", None, menu_message_id.get(chat_id))
    bot.register_next_step_handler_by_chat_id(chat_id, process_withdraw_amount)

def process_withdraw_amount(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    text = message.text.strip().lower()
    balance = get_balance(chat_id)
    
    if text == 'all':
        amount = balance
    else:
        try:
            amount = float(text)
        except:
            safe_edit(chat_id, "❌ Invalid amount!")
            return
    
    if amount <= 0 or amount > balance:
        safe_edit(chat_id, "❌ Invalid amount!")
        return
    
    user_states[chat_id] = {"withdraw_amount": amount}
    safe_edit(chat_id, "💳 Enter your payment details:\n(Wallet address, phone number, etc.)", None, menu_message_id.get(chat_id))
    bot.register_next_step_handler_by_chat_id(chat_id, process_withdraw_details)

def process_withdraw_details(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    details = message.text.strip()
    state = user_states.get(chat_id, {})
    amount = state.get("withdraw_amount", 0)
    
    data = load_data()
    wd_id = len(data.get("withdrawals", [])) + 1
    
    wd_data = {
        "id": wd_id,
        "user_id": chat_id,
        "amount": amount,
        "details": details,
        "status": "pending",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    data.setdefault("withdrawals", []).append(wd_data)
    save_data(data)
    add_balance(chat_id, -amount)
    
    markup = InlineKeyboardMarkup()
    markup.add(ibtn("✅ Approve", callback_data=f"approve_{wd_id}"))
    markup.add(ibtn("❌ Reject", callback_data=f"reject_{wd_id}"))
    
    safe_send(chat_id, f"✅ Withdrawal request #{wd_id} submitted!\n💰 Amount: ${amount:.6f}\n📝 Details: {details}")
    safe_send(ADMIN_ID, f"💳 New withdrawal request #{wd_id}\n👤 User: {chat_id}\n💰 Amount: ${amount:.6f}\n📝 Details: {details}", markup)
    
    user_states.pop(chat_id, None)

def show_withdrawal_history(chat_id):
    data = load_data()
    withdrawals = [w for w in data.get("withdrawals", []) if w["user_id"] == chat_id]
    
    if not withdrawals:
        safe_edit(chat_id, "📋 No withdrawal history.")
        return
    
    text = "📋 Withdrawal History\n━━━━━━━━━━━━━\n"
    for w in reversed(withdrawals[-5:]):
        status_icon = "🟡" if w["status"] == "pending" else "🟢" if w["status"] == "approved" else "🔴"
        text += f"{status_icon} #{w['id']} | ${w['amount']:.6f} | {w['status'].upper()}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(ibtn("🔙 Back", callback_data="close_menu"))
    safe_edit(chat_id, text, markup)

def show_pending_withdrawals(chat_id, msg_id):
    data = load_data()
    pending = [w for w in data.get("withdrawals", []) if w["status"] == "pending"]
    
    if not pending:
        safe_edit(chat_id, "📋 No pending withdrawals.", None, msg_id)
        return
    
    text = "📋 Pending Withdrawals\n━━━━━━━━━━━━━\n"
    markup = InlineKeyboardMarkup(row_width=2)
    
    for w in pending:
        text += f"#{w['id']} | 👤 {w['user_id']} | 💰 ${w['amount']:.6f}\n📝 {w['details']}\n━━━━━━━━━━━━━\n"
        markup.add(ibtn(f"✅ #{w['id']}", callback_data=f"approve_{w['id']}"))
        markup.add(ibtn(f"❌ #{w['id']}", callback_data=f"reject_{w['id']}"))
    
    markup.add(ibtn("🔙 Back", callback_data="admin_back"))
    safe_edit(chat_id, text, markup, msg_id)

def approve_withdrawal(chat_id, wd_id, msg_id):
    data = load_data()
    for w in data.get("withdrawals", []):
        if w["id"] == wd_id and w["status"] == "pending":
            w["status"] = "approved"
            save_data(data)
            safe_send(w["user_id"], f"✅ Withdrawal #{wd_id} approved! 💰 ${w['amount']:.6f}")
            safe_send(chat_id, f"✅ Withdrawal #{wd_id} approved!")
            show_pending_withdrawals(chat_id, msg_id)
            return
    
    safe_edit(chat_id, "❌ Withdrawal not found or already processed.", None, msg_id)

def reject_withdrawal(chat_id, wd_id, msg_id):
    data = load_data()
    for w in data.get("withdrawals", []):
        if w["id"] == wd_id and w["status"] == "pending":
            w["status"] = "rejected"
            add_balance(w["user_id"], w["amount"])
            save_data(data)
            safe_send(w["user_id"], f"❌ Withdrawal #{wd_id} rejected. 💰 Refunded ${w['amount']:.6f}")
            safe_send(chat_id, f"❌ Withdrawal #{wd_id} rejected!")
            show_pending_withdrawals(chat_id, msg_id)
            return
    
    safe_edit(chat_id, "❌ Withdrawal not found or already processed.", None, msg_id)

# ============================================
# --- ADMIN SETTINGS ---
# ============================================
def set_per_otp(message, msg_id):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            safe_send(chat_id, "❌ Amount must be greater than 0!")
            show_admin_panel(chat_id)
            return
        
        data = load_data()
        data["settings"]["per_otp_amount"] = amount
        save_data(data)
        msg = safe_send(chat_id, f"✅ Per OTP amount set to ${amount:.6f}")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    except:
        safe_send(chat_id, "❌ Invalid amount!")
    
    show_admin_panel(chat_id)

def set_min_withdraw(message, msg_id):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            safe_send(chat_id, "❌ Amount must be greater than 0!")
            show_admin_panel(chat_id)
            return
        
        data = load_data()
        data["settings"]["min_withdrawal"] = amount
        save_data(data)
        msg = safe_send(chat_id, f"✅ Minimum withdrawal set to ${amount:.6f}")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    except:
        safe_send(chat_id, "❌ Invalid amount!")
    
    show_admin_panel(chat_id)

def set_cooldown(message, msg_id):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    try:
        seconds = int(message.text.strip())
        if seconds < 0:
            safe_send(chat_id, "❌ Cooldown must be 0 or greater!")
            show_admin_panel(chat_id)
            return
        
        data = load_data()
        data["settings"]["cooldown"] = seconds
        save_data(data)
        msg = safe_send(chat_id, f"✅ Cooldown set to {seconds}s")
        if msg:
            threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 3)).start()
    except:
        safe_send(chat_id, "❌ Invalid number!")
    
    show_admin_panel(chat_id)

# ============================================
# --- BROADCAST ---
# ============================================
def process_broadcast(message, msg_id):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except:
        pass
    
    data = load_data()
    users = data.get("users", [])
    text = message.text
    
    if not text:
        safe_send(chat_id, "❌ No message to broadcast!")
        show_admin_panel(chat_id)
        return
    
    safe_send(chat_id, f"📢 Broadcasting to {len(users)} users...")
    
    success, failed = 0, 0
    for user in users:
        try:
            safe_send(user, f"📢 Broadcast\n━━━━━━━━━━━━━\n{text}")
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    
    msg = safe_send(chat_id, f"✅ Broadcast done!\n✅ Sent: {success}\n❌ Failed: {failed}")
    if msg:
        threading.Thread(target=delete_after_delay, args=(chat_id, msg.message_id, 5)).start()
    show_admin_panel(chat_id)

# ============================================
# --- CALLBACK HANDLER ---
# ============================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    chat_id = call.message.chat.id
    msg_id = call.message.message_id
    data = call.data
    
    if data == "close_menu":
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
        if chat_id in menu_message_id:
            del menu_message_id[chat_id]
        show_main_menu(chat_id)
        return
    
    if data.startswith("service_"):
        service = data.replace("service_", "")
        show_countries(chat_id, service)
        return
    
    if data.startswith("country_"):
        parts = data.split("_")
        service = parts[1]
        country = parts[2]
        request_number(chat_id, service, country)
        return
    
    if data == "back_services":
        show_services(chat_id)
        return
    
    if data == "check_balance":
        show_balance(chat_id)
        return
    
    if data == "request_withdraw":
        request_withdrawal(chat_id)
        return
    
    if data == "withdraw_history":
        show_withdrawal_history(chat_id)
        return
    
    if data.startswith("change_numbers_"):
        parts = data.split("_")
        service = parts[2]
        country = parts[3]
        request_number(chat_id, service, country)
        return
    
    if data.startswith("change_country_"):
        service = data.replace("change_country_", "")
        show_countries(chat_id, service)
        return
    
    # ADMIN CALLBACKS
    if data == "admin_back":
        show_admin_panel(chat_id)
        return
    
    if data == "admin_services":
        show_manage_services(chat_id, msg_id)
        return
    
    if data == "add_service":
        safe_edit(chat_id, "📝 Type the service name to ADD:", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_service)
        return
    
    if data == "remove_service":
        safe_edit(chat_id, "📝 Type the service name to REMOVE:", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_remove_service)
        return
    
    if data == "admin_numbers":
        show_manage_numbers(chat_id, msg_id)
        return
    
    if data == "add_numbers":
        show_add_numbers(chat_id, msg_id)
        return
    
    if data.startswith("addnum_service_"):
        service = data.replace("addnum_service_", "")
        show_add_numbers_country(chat_id, service, msg_id)
        return
    
    if data.startswith("addnum_country_"):
        parts = data.split("_")
        service = parts[2]
        country = parts[3]
        safe_edit(chat_id, f"Send numbers for {service} - {country}\nOne per line or comma separated:", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_add_numbers, service, country, msg_id)
        return
    
    if data == "admin_per_otp":
        safe_edit(chat_id, "💰 Enter new per OTP amount (e.g., 0.005):", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, set_per_otp, msg_id)
        return
    
    if data == "admin_min_withdraw":
        safe_edit(chat_id, "💳 Enter new minimum withdrawal (e.g., 0.50):", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, set_min_withdraw, msg_id)
        return
    
    if data == "admin_cooldown":
        safe_edit(chat_id, "⏳ Enter new cooldown in seconds (e.g., 60):", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, set_cooldown, msg_id)
        return
    
    if data == "admin_withdrawals":
        show_pending_withdrawals(chat_id, msg_id)
        return
    
    if data == "admin_broadcast":
        safe_edit(chat_id, "📢 Send your broadcast message:", None, msg_id)
        bot.register_next_step_handler_by_chat_id(chat_id, process_broadcast, msg_id)
        return
    
    if data.startswith("approve_"):
        wd_id = int(data.replace("approve_", ""))
        approve_withdrawal(chat_id, wd_id, msg_id)
        return
    
    if data.startswith("reject_"):
        wd_id = int(data.replace("reject_", ""))
        reject_withdrawal(chat_id, wd_id, msg_id)
        return

# ============================================
# --- OTP MONITORING THREAD ---
# ============================================
def otp_monitor():
    while True:
        try:
            process_otps()
        except Exception as e:
            print(f"OTP Monitor error: {e}")
        time.sleep(5)

# ============================================
# --- MAIN ---
# ============================================
def show_main_menu(chat_id):
    user_id = chat_id
    username = "User"
    try:
        user = bot.get_chat(chat_id)
        username = user.username or user.first_name
    except:
        pass
    
    text = f"Welcome @{username}"
    msg = safe_send(chat_id, text, get_main_menu(user_id))
    if msg:
        menu_message_id[chat_id] = msg.message_id

if __name__ == "__main__":
    print("🚀 Starting Musky Tech Bot...")
    print("📡 Monitoring BOTH APIs for OTPs...")
    print("📤 Forwarding to group: -1003793881191")
    print("👑 Admin ID: 8017839068")
    print("📌 MBC API: Configured ✅")
    print("📌 REZ API: Configured ✅")
    
    # Start OTP monitor thread
    threading.Thread(target=otp_monitor, daemon=True).start()
    
    # Start timeout checker thread
    threading.Thread(target=check_timeout_requests, daemon=True).start()
    
    print("✅ Both APIs monitoring active!")
    print("🤖 Bot is ready!")
    
    # Start bot
    bot.infinity_polling(timeout=60, long_polling_timeout=55)
