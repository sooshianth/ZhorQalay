// به‌روزرسانی اولیه نشانگرها
document.addEventListener("DOMContentLoaded", function() {
    if (typeof isAuthenticated !== 'undefined' && isAuthenticated) {
        // بازیابی وضعیت پیام‌های جدید از localStorage
        loadNewMessageState();
        
        // جلوگیری از درخواست‌های شبکه قبل از تنظیم userId
        setTimeout(() => {
            // بررسی پیام‌های جدید از سرور
            checkForNewMessages();
            
            // بروزرسانی فوری نشانگرهای پیام‌های جدید
            updateBadges();
        }, 500);
    }
});

// تابع بررسی پیام‌های جدید از سرور
function checkForNewMessages() {
    if (!userId) return;
    
    // بررسی پیام‌های خصوصی جدید
    fetch('/chat/api/chat/unread/count/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.count && data.count > 0) {
            // به‌روزرسانی متغیرهای شمارنده پیام‌های جدید
            newTotalMessages += data.count;
            newPrivateMessages += data.count;
            
            // اگر پیام‌های منحصر به فرد از کاربران خاصی وجود دارد
            if (data.by_user) {
                Object.keys(data.by_user).forEach(senderId => {
                    if (!userNewMessages[senderId]) {
                        userNewMessages[senderId] = 0;
                    }
                    userNewMessages[senderId] += data.by_user[senderId];
                });
            }
            
            // ذخیره وضعیت و به‌روزرسانی نشانگرها
            saveNewMessageState();
            updateBadges();
        }
    })
    .catch(error => {
        console.error('Error checking for new messages:', error);
    });
    
    // همچنین بررسی پیام‌های عمومی جدید
    fetch('/chat/api/chat/global/unread/count/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.count && data.count > 0) {
            // به‌روزرسانی متغیرهای شمارنده پیام‌های عمومی جدید
            newTotalMessages += data.count;
            newGlobalMessages += data.count;
            
            // ذخیره وضعیت و به‌روزرسانی نشانگرها
            saveNewMessageState();
            updateBadges();
        }
    })
    .catch(error => {
        console.error('Error checking for new global messages:', error);
    });
} 