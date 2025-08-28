DOCX Filler (Flutter)

تطبيق فلاتر بسيط لملء قوالب DOCX عبر استبدال المتغيرات داخل ملفات XML الخاصة بالمستند (word/*.xml)، مماثل لآلية fill_docx.py.

المتطلبات:
- Flutter SDK
- لتشغيل سطح المكتب (Linux): حزم البناء (cmake, ninja, clang, pkg-config, libgtk-3-dev)
- لتشغيل Android: Android SDK/Studio
- الويب غير مدعوم حاليًا بسبب اعتماد التطبيق على dart:io للوصول للملفات المحلية.

التشغيل:
```bash
cd /workspace/flutter_docx_filler
flutter run -d linux
```

إذا ظهرت أخطاء أدوات البناء على Linux، قم بتثبيت الحزم:
```bash
sudo apt-get update
sudo apt-get install -y ninja-build cmake clang pkg-config libgtk-3-dev
```

الاستخدام:
1) اختر ملف القالب .docx (يجب أن يحتوي على متغيرات بصيغة {NAME}، {PRICE}، {TOTAL}، {DATE} ... إلخ)
2) اختر ملف بيانات JSON:
   - وضع مفرد: كائن JSON واحد { "NAME": "Acme", ... }
   - وضع الدُفعة: مصفوفة من الكائنات [ { ... }, { ... } ]
3) اختر مسار الإخراج (مفرد) أو مجلد الإخراج (دُفعة)
4) اضغط Run

سيتم استبدال أي نص مطابق لصيغة {KEY} بقيمة KEY من JSON داخل جميع ملفات XML تحت word/ داخل ملف DOCX.

ملاحظة: يجب ألّا تُقسَّم المتغيرات داخل الـ DOCX عبر أكثر من Run في الـ XML.

البنية:
- lib/docx_filler.dart: منطق فتح DOCX كأرشيف ZIP، تعديل XML، وإعادة الحفظ
- lib/main.dart: واجهة مستخدم لاختيار القالب، ملف JSON، وضبط الإخراج

مقارنة مع المشروع الأصلي:
- يحاكي وظيفة fill_docx.py و make_invoice.py برسوميات سطح المكتب عبر Flutter
- التعامل مع ملفات DOCX و JSON يتم محليًا عبر واجهات اختيار الملفات

تطوير إضافي مقترح:
- دعم الويب عبر بدائل dart:io (رفع/تنزيل ملفات بالمتصفح)
- دعم iOS/Android مع أذونات التخزين
- إنشاء نموذج لملء الحقول بدل JSON خارجي
# flutter_docx_filler

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Lab: Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Cookbook: Useful Flutter samples](https://docs.flutter.dev/cookbook)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.
