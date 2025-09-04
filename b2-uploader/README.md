# B2 Uploader Service

خدمة بسيطة (Express + TypeScript) لرفع الملفات مباشرة إلى Backblaze B2 وإرجاع روابط وصول عامة دائمة.

## الإعداد

1) أنشئ Bucket عام (Public) في Backblaze B2 أو فعِّل Public على الBucket الحالي.
2) جهّز مفاتيح: Key ID و Application Key مع صلاحيات الBucket.
3) عيّن المتغيرات في `.env` (انظر `.env.example`):
   - `B2_KEY_ID`
   - `B2_APPLICATION_KEY`
   - `B2_BUCKET_ID`
   - `B2_BUCKET_NAME`
   - `B2_DOWNLOAD_URL` مثل: `https://f003.backblazeb2.com/file/<bucket-name>`

> ملاحظة: الروابط العامة الدائمة تتطلب أن يكون الBucket Public. إن كان Private فستحتاج روابط موقّتة (غير دائمة).

## التشغيل

```bash
npm install
npm run dev
```

المنفذ الافتراضي: `http://localhost:4000`

## الرفع

- المسار: `POST /api/upload`
- نوع الطلب: `multipart/form-data`
- الحقول:
  - `file`: الملف
  - `category`: واحد من القيم: `company-docs | bank-messages | sales-invoices | bank-invoices`
  - `subfolder` (اختياري): مسار فرعي لزيادة التنظيم

الاستجابة مثال:

```json
{
  "fileId": "4_zabc...",
  "fileName": "sales-invoices/2025/09/04/uuid--invoice-123.pdf",
  "category": "sales-invoices",
  "publicUrl": "https://f003.backblazeb2.com/file/my-bucket/sales-invoices/2025/09/04/uuid--invoice-123.pdf",
  "size": 102400,
  "mime": "application/pdf",
  "uploadedAt": "2025-09-04T10:00:00.000Z"
}
```

## الملاحظات الأمنية

- إن كانت الملفات حساسة، استخدم Bucket خاص وروابط موقّتة بدلاً من العامة.
- حدّث حدود الحجم `multer` بحسب احتياجك.
- أضف مصادقة قبل مسارات الرفع حسب أدوار: موظف، مدير، مالية.