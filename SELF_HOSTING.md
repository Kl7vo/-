# قارئ — تشغيل الموقع على خادمك الخاص

يعمل الموقع خارج Emergent بالكامل. لا يحتاج أي مفتاح أو خدمة مدفوعة:
- OCR محلي عبر Tesseract (ملف النموذج داخل `backend/tessdata`).
- الملفات تُحفظ على قرص الخادم.
- قاعدة البيانات MongoDB داخل Docker.

## المتطلبات
خادم Linux فيه Docker و Docker Compose. يكفي VPS بذاكرة 2GB.

## التشغيل
```bash
cp selfhost.env.example selfhost.env
# عدّل JWT_SECRET و ADMIN_PASSWORD داخل selfhost.env
docker compose up -d --build
```
ثم افتح `http://عنوان-الخادم`.

## مع نطاق خاص وشهادة HTTPS
- ضع أمامه Caddy أو Nginx مع Let's Encrypt.
- اجعل `COOKIE_SECURE=true` في `selfhost.env`.
- أعد التشغيل بالأمر `docker compose up -d`.

## ملاحظات
- تسجيل الدخول بـ Google مُعطَّل في هذه النسخة، لأنه خاص بمنصة Emergent. التسجيل بالبريد وكلمة المرور يعمل كاملاً.
- النسخ الاحتياطي: احفظ وحدتي التخزين `mongo_data` و `files_data`.
- التحديث بعد تعديل الكود: `docker compose up -d --build`.
