// متغیرهای سراسری
let currentChatUser = null;
let chatSocket = null;
let currentTab = 'private'; // 'private' یا 'global'
let darkMode = false; // متغیر جدید برای حالت تاریک/روشن
let notificationSound = null; // صدای نوتیفیکیشن
let notificationPermission = false; // دسترسی به نوتیفیکیشن‌های مرورگر

// متغیرهای شمارنده پیام‌های جدید
let newTotalMessages = 0;
let newPrivateMessages = 0;
let newGlobalMessages = 0;
let userNewMessages = {}; // شمارنده پیام‌های هر کاربر

// ذخیره وضعیت پیام‌های جدید در localStorage
function saveNewMessageState() {
    const state = {
        newTotalMessages,
        newPrivateMessages,
        newGlobalMessages,
        userNewMessages
    };
    localStorage.setItem('chatNewMessages', JSON.stringify(state));
}

// بازیابی وضعیت پیام‌های جدید از localStorage
function loadNewMessageState() {
    const savedState = localStorage.getItem('chatNewMessages');
    if (savedState) {
        try {
            const state = JSON.parse(savedState);
            newTotalMessages = state.newTotalMessages || 0;
            newPrivateMessages = state.newPrivateMessages || 0;
            newGlobalMessages = state.newGlobalMessages || 0;
            userNewMessages = state.userNewMessages || {};
            console.log('Loaded message state:', state);
        } catch (e) {
            console.error('Error loading chat state:', e);
        }
    }
    
    // بازیابی وضعیت حالت تاریک/روشن
    darkMode = localStorage.getItem('chatDarkMode') === 'true';
    if (darkMode) {
        document.getElementById('chatWindow').classList.add('dark-mode');
    }
    
    // بارگذاری فایل صوتی نوتیفیکیشن
    loadNotificationSound();
    
    // بررسی دسترسی به نوتیفیکیشن‌های مرورگر
    checkNotificationPermission();
}

// بارگذاری فایل صوتی نوتیفیکیشن
function loadNotificationSound() {
    try {
        // استفاده از Data URL به جای فایل صوتی واقعی
        // این یک صدای "بیپ" کوتاه است
        const soundUrl = 'data:audio/mp3;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
        notificationSound = new Audio(soundUrl);
        notificationSound.volume = 0.5;
        console.log('Notification sound loaded');
    } catch (e) {
        console.error('Error loading notification sound:', e);
    }
}

// بررسی دسترسی به نوتیفیکیشن‌های مرورگر
function checkNotificationPermission() {
    if (!("Notification" in window)) {
        console.log("This browser does not support notifications");
        notificationPermission = false;
        return;
    }
    
    if (Notification.permission === "granted") {
        notificationPermission = true;
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(function (permission) {
            notificationPermission = permission === "granted";
        });
    }
}

// پخش صدای نوتیفیکیشن
function playNotificationSound() {
    if (notificationSound) {
        try {
            notificationSound.currentTime = 0; // بازگشت به ابتدای فایل صوتی
            notificationSound.play().catch(e => console.log('Cannot play notification sound:', e));
        } catch (e) {
            console.error('Error playing notification sound:', e);
        }
    }
}

function formatDateTime(dateString) {
    try {
        const date = new Date(dateString);
        // فرمت ساده تاریخ و زمان
        const time = date.toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit'});
        const today = new Date();
        
        if (date.getDate() === today.getDate() && 
            date.getMonth() === today.getMonth() && 
            date.getFullYear() === today.getFullYear()) {
            return `امروز ${time}`;
        } else {
            const yesterday = new Date(today);
            yesterday.setDate(today.getDate() - 1);
            
            if (date.getDate() === yesterday.getDate() && 
                date.getMonth() === yesterday.getMonth() && 
                date.getFullYear() === yesterday.getFullYear()) {
                return `دیروز ${time}`;
            } else {
                const options = {
                    year: 'numeric',
                    month: 'numeric',
                    day: 'numeric'
                };
                const dateStr = date.toLocaleDateString('fa-IR', options);
                return `${dateStr} ${time}`;
            }
        }
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateString;
    }
}

function updateBadges() {
    console.log('Updating badges:', {
        newTotalMessages,
        newPrivateMessages,
        newGlobalMessages,
        userNewMessages
    });
    
    // بروزرسانی نشانگر اصلی چت
    const chatIcon = document.querySelector('.chat-icon');
    const chatBadge = document.getElementById('chatBadge');
    
    if (newTotalMessages > 0) {
        chatBadge.textContent = newTotalMessages > 99 ? '99+' : newTotalMessages;
        chatBadge.style.display = 'flex';
        chatIcon.classList.add('has-notification');
    } else {
        chatBadge.style.display = 'none';
        chatIcon.classList.remove('has-notification');
    }
    
    // بروزرسانی نشانگر چت خصوصی
    const privateTabBadge = document.getElementById('privateTabBadge');
    if (newPrivateMessages > 0) {
        privateTabBadge.textContent = newPrivateMessages > 99 ? '99+' : newPrivateMessages;
        privateTabBadge.style.display = 'flex';
    } else {
        privateTabBadge.style.display = 'none';
    }
    
    // بروزرسانی نشانگر چت عمومی
    const globalTabBadge = document.getElementById('globalTabBadge');
    if (newGlobalMessages > 0) {
        globalTabBadge.textContent = newGlobalMessages > 99 ? '99+' : newGlobalMessages;
        globalTabBadge.style.display = 'flex';
    } else {
        globalTabBadge.style.display = 'none';
    }
    
    // بروزرسانی نشانگر کاربران
    Object.keys(userNewMessages).forEach(userId => {
        const userItem = document.querySelector(`.user-item[data-user-id="${userId}"]`);
        if (userItem) {
            if (userNewMessages[userId] > 0) {
                userItem.classList.add('has-new-message');
                let badge = userItem.querySelector('.chat-badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'chat-badge';
                    userItem.appendChild(badge);
                }
                badge.textContent = userNewMessages[userId] > 99 ? '99+' : userNewMessages[userId];
                badge.style.display = 'inline-flex';
            } else {
                userItem.classList.remove('has-new-message');
                const badge = userItem.querySelector('.chat-badge');
                if (badge) {
                    badge.remove();
                }
            }
        }
    });
    
    // اگر پیام جدیدی وجود دارد، عنوان صفحه را تغییر دهیم
    updatePageTitle();
    
    // ذخیره وضعیت پیام‌های جدید
    saveNewMessageState();
}

// تغییر عنوان صفحه برای نمایش تعداد پیام‌های جدید
function updatePageTitle() {
    const originalTitle = document.title.replace(/^\(\d+\) /, '');
    
    if (newTotalMessages > 0) {
        document.title = `(${newTotalMessages}) ${originalTitle}`;
    } else {
        document.title = originalTitle;
    }
}

function resetBadge(type, userId = null) {
    if (type === 'global') {
        if (newGlobalMessages > 0) {
            newTotalMessages -= newGlobalMessages;
            newGlobalMessages = 0;
        }
    } else if (type === 'private' && userId) {
        if (userNewMessages[userId]) {
            newPrivateMessages -= userNewMessages[userId];
            newTotalMessages -= userNewMessages[userId];
            userNewMessages[userId] = 0;
        }
    }
    updateBadges();
    saveNewMessageState(); // ذخیره وضعیت جدید
}

function toggleChatWindow() {
    console.log('Toggling chat window');
    const chatWindow = document.getElementById('chatWindow');
    const isVisible = chatWindow.style.display === 'flex';
    
    // تغییر وضعیت نمایش پنجره چت
    chatWindow.style.display = isVisible ? 'none' : 'flex';
    
    // اگر پنجره چت باز شده است
    if (!isVisible) {
        console.log('Chat window opened');
        
        // بارگذاری لیست کاربران
        loadUserList();
        
        // هنگام باز کردن پنجره چت، نشانگرها را بر اساس تب فعلی ریست می‌کنیم
        if (currentTab === 'global') {
            loadGlobalChatHistory();
            resetBadge('global');
        } else if (currentTab === 'private' && currentChatUser) {
            resetBadge('private', currentChatUser);
        }
    } else {
        console.log('Chat window closed');
    }
}

function toggleUserList() {
    const userList = document.getElementById('userList');
    userList.classList.toggle('active');
}

function switchTab(tab) {
    currentTab = tab;
    document.getElementById('privateTabBtn').classList.toggle('active', tab === 'private');
    document.getElementById('globalTabBtn').classList.toggle('active', tab === 'global');
    document.getElementById('privateChatBody').style.display = tab === 'private' ? 'flex' : 'none';
    document.getElementById('globalChatBody').style.display = tab === 'global' ? 'flex' : 'none';
    
    // استفاده از یک متغیر برای جلوگیری از خطای null
    const chatTitle = document.getElementById('chatTitle');
    
    if (tab === 'private' && currentChatUser) {
        if (chatTitle) {
            chatTitle.textContent = `چت با ${document.querySelector('.user-item.active')?.textContent.trim() || 'کاربر'}`;
        }
        resetBadge('private', currentChatUser);
    } else if (tab === 'global') {
        if (chatTitle) {
            chatTitle.textContent = 'چت عمومی';
        }
        loadGlobalChatHistory();
        resetBadge('global');
    }
    
    // ذخیره تب فعلی در localStorage
    localStorage.setItem('currentChatTab', tab);
}

// تابع جدید برای تغییر حالت تاریک/روشن
function toggleDarkMode() {
    darkMode = !darkMode;
    document.getElementById('chatWindow').classList.toggle('dark-mode', darkMode);
    localStorage.setItem('chatDarkMode', darkMode.toString());
}

// نمایش نوتیفیکیشن برای پیام جدید
function showNewMessageNotification(message, sender, isGlobal = false) {
    // پخش صدای نوتیفیکیشن
    playNotificationSound();
    
    // نمایش نوتیفیکیشن مرورگر
    if (notificationPermission) {
        showBrowserNotification(message, sender, isGlobal);
    } else {
        // اگر دسترسی به نوتیفیکیشن‌های مرورگر نداریم، از نوتیفیکیشن داخل برنامه استفاده می‌کنیم
        showInAppNotification(message, sender, isGlobal);
    }
    
    // تغییر عنوان صفحه
    updatePageTitle();
}

// نمایش نوتیفیکیشن مرورگر
function showBrowserNotification(message, sender, isGlobal = false) {
    try {
        const title = isGlobal ? 'پیام جدید در چت عمومی' : `پیام جدید از ${sender}`;
        const notification = new Notification(title, {
            body: message.length > 50 ? message.substring(0, 50) + '...' : message,
            icon: "/static/chat/images/chat-icon.png",
            silent: true // صدا را خودمان مدیریت می‌کنیم
        });
        
        notification.onclick = function() {
            window.focus();
            toggleChatWindow();
            
            if (isGlobal) {
                switchTab('global');
            } else {
                // پیدا کردن کاربر فرستنده و شروع چت
                const userItem = document.querySelector(`.user-item[data-username="${sender}"]`);
                if (userItem) {
                    const userId = userItem.dataset.userId;
                    startChat(userId, sender);
                }
            }
        };
    } catch (e) {
        console.error('Error showing browser notification:', e);
    }
}

// نمایش نوتیفیکیشن داخل برنامه
function showInAppNotification(message, sender, isGlobal = false) {
    // حذف هر نوتیفیکیشن قبلی
    const existingNotification = document.querySelector('.browser-notification');
    if (existingNotification) {
        existingNotification.remove();
    }
    
    // ایجاد نوتیفیکیشن جدید
    const notification = document.createElement('div');
    notification.className = 'browser-notification';
    
    const title = document.createElement('div');
    title.className = 'notification-title';
    title.textContent = isGlobal ? 'پیام جدید در چت عمومی' : `پیام جدید از ${sender}`;
    notification.appendChild(title);
    
    const body = document.createElement('div');
    body.className = 'notification-body';
    body.textContent = message.length > 50 ? message.substring(0, 50) + '...' : message;
    notification.appendChild(body);
    
    const closeButton = document.createElement('button');
    closeButton.className = 'notification-close';
    closeButton.innerHTML = '&times;';
    closeButton.onclick = function() {
        notification.remove();
    };
    notification.appendChild(closeButton);
    
    document.body.appendChild(notification);
    
    // نمایش نوتیفیکیشن
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // حذف خودکار نوتیفیکیشن بعد از 5 ثانیه
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
    
    // کلیک روی نوتیفیکیشن
    notification.addEventListener('click', function() {
        toggleChatWindow();
        if (isGlobal) {
            switchTab('global');
        } else {
            // پیدا کردن کاربر فرستنده و شروع چت
            const userItem = document.querySelector(`.user-item[data-username="${sender}"]`);
            if (userItem) {
                const userId = userItem.dataset.userId;
                startChat(userId, sender);
            }
        }
        notification.remove();
    });
}

// اضافه کردن دکمه تغییر حالت تاریک/روشن هنگام بارگذاری صفحه
document.addEventListener('DOMContentLoaded', function() {
    loadNewMessageState();
    updateBadges();
    
    // بازیابی تب فعلی از localStorage
    const savedTab = localStorage.getItem('currentChatTab');
    if (savedTab) {
        switchTab(savedTab);
    }
    
    // بازیابی کاربر فعلی از localStorage
    const savedUserId = localStorage.getItem('currentChatUser');
    const savedUsername = localStorage.getItem('currentChatUsername');
    if (savedUserId && savedUsername) {
        currentChatUser = savedUserId;
        const chatTitle = document.getElementById('chatTitle');
        if (chatTitle) {
            chatTitle.textContent = `چت با ${savedUsername}`;
        }
    }
    
    // افزودن دکمه تغییر حالت تاریک/روشن
    const chatHeaderActions = document.querySelector('.chat-header-actions');
    if (chatHeaderActions) {
        const darkModeToggle = document.createElement('button');
        darkModeToggle.innerHTML = '<i class="fas fa-moon"></i>';
        darkModeToggle.title = 'تغییر حالت نمایش';
        darkModeToggle.onclick = toggleDarkMode;
        
        // افزودن دکمه قبل از آخرین دکمه (دکمه بستن)
        chatHeaderActions.insertBefore(darkModeToggle, chatHeaderActions.lastChild);
    }
}); 