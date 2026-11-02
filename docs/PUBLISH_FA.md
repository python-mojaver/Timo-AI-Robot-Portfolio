# انتشار نسخهٔ بک‌اند تیمو

این بسته برای مخزن جداگانهٔ بک‌اند آماده شده است. مخزن عمومی `HTNRobotAssistant` که بررسی شد، پروژهٔ Android است؛ آن را با کد Python جایگزین نکنید.

## آماده‌سازی

۱. مخزن عمومی `python-mojaver/Timo-AI-Robot-Portfolio` ساخته شده است. مخزن خصوصی قدیمی `Timo-AI-Robot-Assistant` را نگه دارید. این بسته را در پوشه‌ای جدا استخراج و فقط همین نسخهٔ عمومی را منتشر کنید.

۲. در پوشهٔ جداگانهٔ همین بسته PowerShell باز کنید و اجرا کنید:

```powershell
git init -b main
git add .
python scripts/check_public_files.py
git diff --cached --stat
```

بررسی باید `Public-file check: OK` بدهد. فایل‌های `.env`، دیتابیس، عکس چهره، مدل، بکاپ و فایل قیمت نباید در فهرست staged باشند. اگر مخزن بک‌اند از قبل Private وجود دارد، ابتدا آدرس همان را مشخص کنید و این مراحل ساخت مخزن تازه را اجرا نکنید.

۳. سپس:

```powershell
git commit -m "Publish Timo FastAPI and LangGraph portfolio backend"
git remote add origin https://github.com/python-mojaver/Timo-AI-Robot-Portfolio.git
git push -u origin main
```

این آدرس، مخزن عمومی جدید و مقصد انتشار بسته است؛ ساخته‌شدن مخزن به معنی بارگذاری کدها نیست. پس از push موفق، صفحهٔ مخزن و تب Actions را باز کنید. اگر remote از قبل تعریف شده است، آن را بدون بررسی تغییر ندهید.

## رزومه

پس از تأیید انتشار موفق، لینک بک‌اند و لینک مستقل Android را به بخش تیمو اضافه می‌کنیم. جزئیات قابل استفاده در `RESUME_FA.md` نوشته شده‌اند. تا پیش از آن لینک برنامه‌ریزی‌شده را به‌عنوان پروژهٔ منتشرشده معرفی نکنید.
