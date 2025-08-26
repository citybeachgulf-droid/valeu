// static/service-worker.js

self.addEventListener("install", function(event) {
  console.log("✅ Service Worker تم تثبيته");
});

self.addEventListener("activate", function(event) {
  console.log("✅ Service Worker مفعل");
});

// تجربة: عند وصول إشعار Push
self.addEventListener("push", function(event) {
  console.log("📩 وصل إشعار:", event.data.text());
  const data = event.data.json();

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/icon.png" // تقدر تحط أي صورة كأيقونة
    })
  );
});
