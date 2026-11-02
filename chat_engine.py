import json
import os
import re
from urllib import error as urllib_error
from urllib import request as urllib_request

from dotenv import load_dotenv

from database import get_connection


# متغیرهای محیطی پروژه را از فایل .env می‌خوانیم.
load_dotenv()

# آدرس دائمی Workflow منتشرشده در n8n.
# اگر بعداً آدرس عوض شد، کافی است N8N_WEBHOOK_URL را در .env تغییر بدهید.
N8N_WEBHOOK_URL = os.getenv(
    "N8N_PRIME_WEBHOOK_URL",
    os.getenv("N8N_WEBHOOK_URL", "http://127.0.0.1:5678/webhook/htn-prime-chat")
).strip()

N8N_TIMEOUT_SECONDS = 25


# ==========================================
# وضعیت فعلی مکالمه
# ==========================================

current_results = []
current_index = 0
product_context_active = False

# وقتی کاربر می‌پرسد چند مدل داریم،
# منتظر تایید او برای شروع معرفی می‌مانیم.
waiting_for_list_confirmation = False


# عبارت‌هایی که با اطمینان نشان می‌دهند کاربر درباره کاتالوگ فروشگاه
# سؤال کرده است. نام دقیق محصولات و دسته‌بندی‌ها نیز جداگانه از دیتابیس
# بررسی می‌شوند؛ بنابراین لازم نیست کاربر حتماً کلمه «محصول» را بگوید.
CATALOG_INTENT_PHRASES = {
    "محصول", "محصولات", "کالا", "کالاها", "کالای",
    "کاتالوگ", "موجودی فروشگاه", "موجود دارید", "موجود دارین",
    "برای خرید", "قصد خرید", "کد محصول", "کد کالا",
    "محصولات شما", "کالاهای شما"
}

CONFIRM_LIST_COMMANDS = {
    "بله", "آره", "اره", "آری", "بگو", "بله بگو", "آره بگو",
    "معرفی کن", "همشونو بگو", "همه رو بگو", "همشون رو بگو"
}

NEXT_PRODUCT_COMMANDS = {
    "بعدی", "مدل بعدی", "یکی دیگه", "یکی دیگر", "بعدیش",
    "بله", "آره", "اره", "آری", "بگو", "بله بگو", "آره بگو"
}

PRICE_COMMANDS = {"قیمتش چنده", "قیمت چنده", "قیمتش", "قیمت"}

CHEAPER_COMMANDS = {
    "ارزون‌تر", "ارزان‌تر", "ارزون تر", "ارزان تر",
    "مدل ارزون‌تر", "مدل ارزان‌تر", "ارزونتر", "ارزانتر"
}

EXPENSIVE_COMMANDS = {
    "گرون‌تر", "گران‌تر", "گرون تر", "گران تر",
    "مدل گرون‌تر", "مدل گران‌تر", "گرونتر", "گرانتر"
}

AVAILABLE_COMMANDS = {
    "فقط موجود", "فقط موجودها", "موجودها", "موجودارو بگو",
    "موجودها رو بگو", "فقط کالاهای موجود"
}


def normalize_text(text):
    """متن فارسی را برای مقایسه فرمان‌ها یکدست می‌کند."""

    normalized = str(text or "").strip().lower()
    normalized = normalized.replace("ي", "ی").replace("ك", "ک")
    normalized = normalized.replace("‌", " ")
    normalized = re.sub(r"[؟?!،,.؛:]+", " ", normalized)
    return " ".join(normalized.split())


def clear_product_context():
    """حالت معرفی محصول را هنگام ورود به گفت‌وگوی عمومی پاک می‌کند."""

    global current_results
    global current_index
    global waiting_for_list_confirmation
    global product_context_active

    current_results = []
    current_index = 0
    waiting_for_list_confirmation = False
    product_context_active = False


# ==========================================
# دریافت پاسخ گفت‌وگوی عمومی از n8n / Gemini
# ==========================================

def ask_n8n(user_text):
    """
    پیام‌هایی را که در دیتابیس محصول پاسخی ندارند، به n8n می‌فرستد.
    در صورت قطع اینترنت، خطای n8n یا پاسخ نامعتبر، None برمی‌گرداند
    تا موتور اصلی بتواند پیام جایگزین مناسبی نمایش دهد.
    """

    if not N8N_WEBHOOK_URL:
        print("n8n Error: N8N_WEBHOOK_URL is empty.")
        return None

    # چون قبل از فراخوانی این تابع هیچ محصولی در دیتابیس پیدا نشده،
    # این توضیح مانع ساختن قیمت، موجودی یا مشخصات جعلی توسط مدل می‌شود.
    safe_message = (
        f"پیام کاربر: {user_text}\n\n"
        "اطلاع داخلی: این پیام با هیچ محصولی در دیتابیس فروشگاه تطبیق "
        "پیدا نکرده است. اگر سؤال درباره محصول، قیمت، موجودی یا مشخصات "
        "کالا است، هیچ اطلاعاتی نساز و کوتاه بگو این مورد در اطلاعات "
        "فروشگاه پیدا نشد. اگر پیام عمومی یا گفت‌وگویی است، دقیق، مفید "
        "و به زبان فارسی پاسخ بده. مستقیم سراغ پاسخ برو و نقش خودت را "
        "با جمله‌هایی مثل «من دستیار فروش هستم» معرفی نکن."
    )

    payload = json.dumps(
        {"message": safe_message},
        ensure_ascii=False
    ).encode("utf-8")

    http_request = urllib_request.Request(
        N8N_WEBHOOK_URL,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(
            http_request,
            timeout=N8N_TIMEOUT_SECONDS
        ) as http_response:
            response_text = http_response.read().decode("utf-8-sig")

        response_data = json.loads(response_text)

        # بعضی تنظیمات n8n خروجی را به صورت یک آرایه تک‌عضوی برمی‌گردانند.
        if isinstance(response_data, list):
            if not response_data:
                return None
            response_data = response_data[0]

        if not isinstance(response_data, dict):
            print("n8n Error: response is not a JSON object.")
            return None

        reply = response_data.get("reply") or response_data.get("text")

        if not reply:
            print("n8n Error: reply field is empty.")
            return None

        return str(reply).strip()

    except urllib_error.HTTPError as http_error:
        print(
            "n8n HTTP Error:",
            http_error.code,
            http_error.reason
        )
    except urllib_error.URLError as connection_error:
        print("n8n Connection Error:", connection_error.reason)
    except (TimeoutError, json.JSONDecodeError) as response_error:
        print("n8n Response Error:", response_error)
    except Exception as unexpected_error:
        print("n8n Unexpected Error:", unexpected_error)

    return None


# ==========================================
# کلمات پرکاربردی که ربطی به نام محصول ندارند
# و نباید در جستجو به عنوان شرط اجباری در نظر گرفته شوند
# ==========================================

STOP_WORDS = {
    "چه", "محصولاتی", "کالاهایی",
    "سلام", "خداحافظ", "ممنون", "مرسی", "لطفا", "لطفاً",
    "میخوام", "می‌خوام", "میخواستم", "می‌خواستم", "میخواهم",
    "دارید", "دارین", "داری", "داریم", "دارم",
    "هست", "هستش", "هستید", "میباشد", "می‌باشد",
    "یک", "یه", "این", "اون", "آن", "که", "را", "رو",
    "برای", "من", "شما", "ما", "با", "از", "به", "در",
    "چیه", "چیست", "چطور", "چگونه", "آیا", "ایا",
    "بگو", "بگید", "معرفی", "کن", "کنید",
    "قیمتش", "قیمت", "چنده", "چند",
    "محصول", "محصولات", "کالا", "کالاها", "کالای",
    "فروشگاه", "کاتالوگ", "خرید", "موجود", "موجودی"
}


# ==========================================
# تبدیل قیمت به فرمت خوانا
# ==========================================

def format_price(price_toman):
    if price_toman is None:
        return "ناموجود"

    return f"{int(price_toman):,} تومان"


# ==========================================
# جستجوی محصولات
# ==========================================

def extract_product_keywords(user_text):
    """کلمه‌های معنادار برای جست‌وجوی کاتالوگ را استخراج می‌کند."""

    normalized = normalize_text(user_text)
    raw_words = [
        word.strip()
        for word in normalized.split()
        if len(word.strip()) >= 2
    ]

    return [word for word in raw_words if word not in STOP_WORDS]


def get_all_products(limit=50):
    """برای سؤال‌های کلی مانند «چه محصولاتی دارید؟» استفاده می‌شود."""

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM products ORDER BY product_name LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def search_products_strong(user_text, limit=50):
    """
    فقط فیلدهای هویتی محصول را بررسی می‌کند.

    توضیحات محصول عمداً اینجا جست‌وجو نمی‌شود تا یک کلمه عمومی در توضیحات
    باعث نشود سؤال غیرمحصولی به اشتباه پاسخ محصول بگیرد.
    """

    keywords = extract_product_keywords(user_text)

    if not keywords:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    score_parts = []
    where_parts = []
    score_params = []
    where_params = []

    for word in keywords:
        like = f"%{word}%"
        match_expr = """
            (
                CASE WHEN product_name LIKE ? THEN 6 ELSE 0 END +
                CASE WHEN product_code LIKE ? THEN 8 ELSE 0 END +
                CASE WHEN category LIKE ? THEN 5 ELSE 0 END
            )
        """

        score_parts.append(match_expr)
        score_params.extend([like, like, like])
        where_parts.append(f"({match_expr} > 0)")
        where_params.extend([like, like, like])

    score_sql = " + ".join(score_parts)
    where_sql = " OR ".join(where_parts)

    sql = f"""
        SELECT *, ({score_sql}) AS match_score
        FROM products
        WHERE {where_sql}
        ORDER BY match_score DESC
        LIMIT ?
    """

    cursor.execute(
        sql,
        score_params + where_params + [limit]
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def has_catalog_intent(user_text):
    """وجود عبارت صریح مربوط به محصولات فروشگاه را تشخیص می‌دهد."""

    normalized = normalize_text(user_text)
    return any(
        phrase in normalized
        for phrase in CATALOG_INTENT_PHRASES
    )


def search_products_multi(user_text, limit=50):
    conn = get_connection()
    cursor = conn.cursor()

    keywords = extract_product_keywords(user_text)

    if not keywords:
        conn.close()
        return []

    # برای هر کلمه یک شرط OR جدا می‌سازیم و در نهایت با UNION/امتیازدهی
    # ردیف‌هایی که با بیشترین تعداد کلمه مچ شدن رو اول برمی‌گردونیم.
    # یعنی کافیه فقط بخشی از کلمات (نه لزوما همه) مچ بشن.
    score_parts = []
    where_parts = []
    score_params = []
    where_params = []

    for word in keywords:
        like = f"%{word}%"

        match_expr = """
            (
                CASE WHEN product_name LIKE ? THEN 1 ELSE 0 END +
                CASE WHEN description LIKE ? THEN 1 ELSE 0 END +
                CASE WHEN color LIKE ? THEN 1 ELSE 0 END +
                CASE WHEN size LIKE ? THEN 1 ELSE 0 END +
                CASE WHEN product_code LIKE ? THEN 1 ELSE 0 END +
                CASE WHEN category LIKE ? THEN 1 ELSE 0 END
            )
        """

        score_parts.append(match_expr)
        score_params.extend([like, like, like, like, like, like])

        where_parts.append(f"({match_expr} > 0)")
        where_params.extend([like, like, like, like, like, like])

    score_sql = " + ".join(score_parts)
    where_sql = " OR ".join(where_parts)

    sql = f"""
        SELECT *, ({score_sql}) AS match_score
        FROM products
        WHERE {where_sql}
        ORDER BY match_score DESC
        LIMIT ?
    """

    # ترتیب پارامترها باید دقیقاً با ترتیب "?" در SQL یکی باشه:
    # اول همه‌ی پارامترهای score_sql، بعد همه‌ی پارامترهای where_sql
    full_params = score_params + where_params
    full_params.append(limit)

    cursor.execute(sql, full_params)

    rows = cursor.fetchall()
    conn.close()

    return rows


# ==========================================
# تبدیل محصول به متن قابل گفتن توسط ربات
# ==========================================

def product_to_text(product):
    name = product["product_name"]
    color = product["color"]
    size = product["size"]

    text = name

    if color:
        text += f"، رنگ {color}"

    if size:
        text += f"، سایز {size}"

    if product["available"] == 0 or product["price_toman"] is None:
        text += "، این مدل فعلاً ناموجوده"
    else:
        text += f"، قیمت {format_price(product['price_toman'])}"

    return text


# ==========================================
# فقط محصولات موجود
# ==========================================

def get_available_results(results):
    return [
        product
        for product in results
        if product["available"] == 1
        and product["price_toman"] is not None
    ]


# ==========================================
# پیدا کردن مدل ارزان‌تر
# ==========================================

def get_cheaper_product():
    global current_results
    global current_index

    if not current_results:
        return None

    current_product = current_results[current_index]
    current_price = current_product["price_toman"]

    if current_price is None:
        available = get_available_results(current_results)

        if not available:
            return None

        return min(
            available,
            key=lambda item: item["price_toman"]
        )

    cheaper = [
        product
        for product in current_results
        if product["price_toman"] is not None
        and product["price_toman"] < current_price
    ]

    if not cheaper:
        return None

    return max(
        cheaper,
        key=lambda item: item["price_toman"]
    )


# ==========================================
# پیدا کردن مدل گران‌تر
# ==========================================

def get_more_expensive_product():
    global current_results
    global current_index

    if not current_results:
        return None

    current_product = current_results[current_index]
    current_price = current_product["price_toman"]

    if current_price is None:
        available = get_available_results(current_results)

        if not available:
            return None

        return min(
            available,
            key=lambda item: item["price_toman"]
        )

    expensive = [
        product
        for product in current_results
        if product["price_toman"] is not None
        and product["price_toman"] > current_price
    ]

    if not expensive:
        return None

    return min(
        expensive,
        key=lambda item: item["price_toman"]
    )


# ==========================================
# موتور اصلی گفتگو
# ==========================================

def answer_query(user_text, allow_ai=True):
    global current_results
    global current_index
    global waiting_for_list_confirmation
    global product_context_active

    text = user_text.strip()
    normalized = normalize_text(text)

    if normalized in {"exit", "quit", "خروج"}:
        return "__EXIT__"

    # این فرمان‌ها فقط زمانی معنی محصولی دارند که واقعاً در حالت محصول باشیم.
    if (
        product_context_active
        and waiting_for_list_confirmation
        and normalized in CONFIRM_LIST_COMMANDS
    ):
        if not current_results:
            clear_product_context()
            return "محصولی برای معرفی ندارم."

        waiting_for_list_confirmation = False
        current_index = 0
        product = current_results[current_index]
        return (
            product_to_text(product)
            + "، دوست دارید مدل بعدی رو هم معرفی کنم؟"
        )

    if (
        product_context_active
        and current_results
        and normalized in NEXT_PRODUCT_COMMANDS
    ):
        current_index += 1

        if current_index >= len(current_results):
            clear_product_context()
            return "مدل دیگه‌ای در این جستجو ندارم."

        product = current_results[current_index]
        return (
            product_to_text(product)
            + "، دوست دارید مدل بعدی رو هم معرفی کنم؟"
        )

    if (
        product_context_active
        and current_results
        and normalized in PRICE_COMMANDS
    ):
        product = current_results[current_index]

        if product["price_toman"] is None:
            return "این مدل در حال حاضر ناموجوده."

        return (
            f"قیمت این مدل "
            f"{format_price(product['price_toman'])} هست."
        )

    if (
        product_context_active
        and current_results
        and normalized in CHEAPER_COMMANDS
    ):
        product = get_cheaper_product()

        if product is None:
            return "مدل ارزون‌تری در این نتایج ندارم."

        current_index = current_results.index(product)
        return "یک مدل ارزون‌تر دارم. " + product_to_text(product)

    if (
        product_context_active
        and current_results
        and normalized in EXPENSIVE_COMMANDS
    ):
        product = get_more_expensive_product()

        if product is None:
            return "مدل گرون‌تری در این نتایج ندارم."

        current_index = current_results.index(product)
        return "یک مدل گرون‌تر دارم. " + product_to_text(product)

    if (
        product_context_active
        and current_results
        and normalized in AVAILABLE_COMMANDS
    ):
        available = get_available_results(current_results)

        if not available:
            return "از این جستجو محصول موجودی پیدا نکردم."

        current_results = available
        current_index = 0
        return (
            "حتماً، فقط مدل‌های موجود رو در نظر می‌گیرم. "
            + product_to_text(current_results[0])
            + "، مدل بعدی رو هم بگم؟"
        )

    # فقط نام، دسته‌بندی و کد محصول می‌توانند بدون کلمه «محصول»
    # یک پیام را وارد مسیر دیتابیس کنند.
    strong_results = search_products_strong(text)
    product_request = bool(strong_results) or has_catalog_intent(text)

    count_words = {"چند تا", "چندتا", "چند مدل", "تعداد"}

    if product_request and any(word in normalized for word in count_words):
        search_text = normalized
        remove_words = [
            "چند تا", "چندتا", "چند مدل", "تعداد", "دارید", "دارین",
            "داریم", "داری", "موجود دارید", "موجوده", "هست"
        ]

        for word in remove_words:
            search_text = search_text.replace(word, " ")

        search_text = " ".join(search_text.split())
        results = search_products_strong(search_text)

        if not results and not extract_product_keywords(search_text):
            results = get_all_products()

        if not results and has_catalog_intent(text):
            results = search_products_multi(search_text)

        if not results:
            clear_product_context()
            return "محصولی با این مشخصات پیدا نکردم."

        current_results = results
        current_index = 0
        waiting_for_list_confirmation = True
        product_context_active = True

        return (
            f"{len(results)} مدل از این محصول داریم. "
            "دوست دارید همه مدل‌ها رو یکی‌یکی معرفی کنم؟"
        )

    # هر پیام غیرمحصولی مستقیم به Gemini می‌رود. با ورود به این مسیر،
    # وضعیت محصول قبلی پاک می‌شود تا پاسخ سوم یا «بله» محصول بعدی نشود.
    if not product_request:
        clear_product_context()
        if not allow_ai:
            return "محصولی با این مشخصات در کاتالوگ پیدا نکردم. نام یا کد محصول رو بگید."
        ai_response = ask_n8n(text)

        if ai_response:
            return ai_response

        return "فعلاً ارتباط با پاسخ‌گوی هوشمند برقرار نیست. دوباره تلاش کنید."

    # مسیر محصول: نتایج مطمئن مقدم‌اند. جست‌وجوی توضیحات فقط برای
    # درخواست‌هایی انجام می‌شود که صریحاً درباره کاتالوگ هستند.
    results = strong_results

    if not results:
        if not extract_product_keywords(text):
            results = get_all_products()
        else:
            results = search_products_multi(text)

    if not results:
        clear_product_context()
        return "محصولی با این مشخصات پیدا نکردم."

    current_results = results
    current_index = 0
    waiting_for_list_confirmation = False
    product_context_active = True

    product = current_results[0]
    return (
        product_to_text(product)
        + "، دوست دارید مدل بعدی رو هم معرفی کنم؟"
    )


# ==========================================
# اجرای مستقیم از ترمینال
# ==========================================

if __name__ == "__main__":

    print("تیمو آماده است.")

    while True:

        user_text = input("\nشما: ").strip()

        response = answer_query(user_text)

        if response == "__EXIT__":
            break

        print("ربات:", response)
