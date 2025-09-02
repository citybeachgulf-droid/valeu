// static/service-worker.js

self.addEventListener("install", function(event) {
  console.log("✅ Service Worker تم تثبيته");
});

self.addEventListener("activate", function(event) {
  console.log("✅ Service Worker مفعل");
});

// تجربة: عند وصول إشعار Push
self.addEventListener("push", function(event) {
  try {
    const data = event.data ? event.data.json() : { title: "إشعار", body: "لديك إشعار جديد" };

    // بث رسالة لكل العملاء المفتوحين لتشغيل النغمة محلياً
    const broadcastToClients = async () => {
      const clientList = await clients.matchAll({ type: "window", includeUncontrolled: true });
      clientList.forEach((client) => {
        try {
          client.postMessage({
            type: "PUSH_NOTIFICATION",
            title: data.title || "إشعار",
            body: data.body || "لديك إشعار جديد",
            click_url: data.click_url || "/"
          });
        } catch (_) {}
      });
    };

    event.waitUntil(Promise.all([
      self.registration.showNotification(data.title || "إشعار", {
        body: data.body || "لديك إشعار جديد",
        icon: "/static/icon.png",
        data: data.click_url || "/"
      }),
      broadcastToClients()
    ]));
  } catch (e) {
    event.waitUntil(
      self.registration.showNotification("إشعار", { body: "لديك إشعار جديد", icon: "/static/icon.png" })
    );
  }
});

self.addEventListener("notificationclick", function(event) {
  event.notification.close();
  const target = event.notification.data || "/";
  event.waitUntil(clients.openWindow(target));
});
