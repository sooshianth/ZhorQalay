// توابع مربوط به بارگذاری اطلاعات و ارتباط با سرور
function loadUserList() {
    console.log('Loading user list...');
    
    // نمایش پیام در حال بارگذاری
    const userListItems = document.getElementById('userListItems');
    userListItems.innerHTML = '<div class="loading-message">در حال بارگذاری کاربران...</div>';
    
    fetch('/chat/api/online-users/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'include'
    })
        .then(response => {
            console.log('Fetch Users Response Status:', response.status);
            if (!response.ok) {
                throw new Error('Failed to fetch users: ' + response.statusText);
            }
            return response.json();
        })
        .then(users => {
            console.log('Users received:', users);
            if (users.error) {
                console.error('Error from API:', users.error);
                userListItems.innerHTML = '<div class="error-message">خطا در دریافت لیست کاربران: ' + users.error + '</div>';
                return;
            }
            
            userListItems.innerHTML = '';
            
            if (users.length === 0) {
                userListItems.innerHTML = '<div class="empty-message">کاربر دیگری در سیستم موجود نیست</div>';
                return;
            }
            
            users.forEach(user => {
                if (user.id !== userId) {
                    const userItem = document.createElement('div');
                    userItem.className = 'user-item';
                    const thisUserId = user.id.toString();
                    userItem.dataset.userId = thisUserId;
                    
                    // اضافه کردن نام کاربر
                    const userName = document.createElement('span');
                    userName.textContent = user.username;
                    userItem.appendChild(userName);
                    
                    // اضافه کردن وضعیت آنلاین
                    const userStatus = document.createElement('span');
                    userStatus.className = 'user-status online';
                    userItem.appendChild(userStatus);
                    
                    // اضافه کردن نشانگر پیام جدید اگر وجود داشته باشد
                    if (userNewMessages[thisUserId] && userNewMessages[thisUserId] > 0) {
                        userItem.classList.add('has-new-message');
                        const badge = document.createElement('span');
                        badge.className = 'chat-badge';
                        badge.textContent = userNewMessages[thisUserId] > 99 ? '99+' : userNewMessages[thisUserId];
                        badge.style.display = 'inline-flex';
                        userItem.appendChild(badge);
                    }
                    
                    userItem.onclick = () => startChat(user.id, user.username);
                    userListItems.appendChild(userItem);
                }
            });
            
            // اگر قبلا چت با کاربری باز بوده، آن کاربر را انتخاب کنیم
            if (currentChatUser) {
                const activeUser = document.querySelector(`.user-item[data-user-id="${currentChatUser}"]`);
                if (activeUser) {
                    activeUser.classList.add('active');
                }
            }
        })
        .catch(error => {
            console.error('Error fetching users:', error);
            // نمایش پیام خطا به کاربر
            userListItems.innerHTML = '<div class="error-message">خطا در بارگذاری لیست کاربران: ' + error.message + '</div>';
        });
}

function startChat(userId, username) {
    // فعال کردن تب چت خصوصی
    switchTab('private');
    
    currentChatUser = userId;
    
    // استفاده از chatTitle به جای .chat-header span
    const chatTitle = document.getElementById('chatTitle');
    if (chatTitle) {
        chatTitle.textContent = `چت با ${username}`;
    }
    
    // نشانه‌گذاری کاربر انتخاب شده
    const userItems = document.querySelectorAll('.user-item');
    userItems.forEach(item => {
        item.classList.remove('active');
        if (parseInt(item.dataset.userId) === userId) {
            item.classList.add('active');
            
            // حذف نشانگر "پیام جدید" از کاربر
            item.classList.remove('has-new-message');
            const badge = item.querySelector('.chat-badge');
            if (badge) {
                badge.remove();
            }
        }
    });
    
    // ریست کردن نشانگر پیام جدید برای این کاربر
    resetBadge('private', userId.toString());
    
    // ذخیره کاربر فعلی در localStorage برای حفظ وضعیت بعد از رفرش
    localStorage.setItem('currentChatUser', userId);
    localStorage.setItem('currentChatUsername', username);
    
    toggleUserList();
    loadChatHistory();
}

function loadChatHistory() {
    if (!currentChatUser) {
        console.log('No user selected for chat history');
        return;
    }
    
    const chatBody = document.getElementById('privateChatBody');
    chatBody.innerHTML = '<div class="loading-message">در حال بارگذاری پیام‌ها...</div>';
    
    fetch(`/chat/api/chat/history/${currentChatUser}/`, {
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include'
    })
        .then(response => {
            console.log('Chat History Response Status:', response.status);
            if (!response.ok) {
                throw new Error('Failed to fetch chat history: ' + response.statusText);
            }
            return response.json();
        })
        .then(messages => {
            console.log('Chat History:', messages);
            chatBody.innerHTML = '';
            
            if (messages.length === 0) {
                chatBody.innerHTML = '<div class="empty-message">هنوز پیامی ارسال نشده است</div>';
                return;
            }
            
            // مرتب‌سازی پیام‌ها بر اساس زمان
            messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            // نمایش پیام‌ها
            messages.forEach(msg => {
                // اضافه کردن شناسه فرستنده و گیرنده پیام برای نمایش صحیح
                msg.sender_id = parseInt(msg.sender_id);
                msg.receiver_id = parseInt(msg.receiver_id);
                displayPrivateMessage(msg);
            });
            
            // اسکرول به آخرین پیام
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight;
            }, 100);
            
            // علامت‌گذاری پیام‌ها به عنوان خوانده‌شده
            markMessagesAsRead(currentChatUser);
        })
        .catch(error => {
            console.error('Error fetching chat history:', error);
            chatBody.innerHTML = '<div class="error-message">خطا در بارگذاری پیام‌ها. لطفا دوباره تلاش کنید.</div>';
        });
}

function loadGlobalChatHistory() {
    const chatBody = document.getElementById('globalChatBody');
    chatBody.innerHTML = '<div class="loading-message">در حال بارگذاری پیام‌ها...</div>';
    
    fetch('/chat/api/chat/global/', {
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include'
    })
        .then(response => {
            console.log('Global Chat History Response Status:', response.status);
            if (!response.ok) {
                throw new Error('Failed to fetch global chat history: ' + response.statusText);
            }
            return response.json();
        })
        .then(messages => {
            console.log('Global Chat History:', messages);
            chatBody.innerHTML = '';
            
            if (messages.length === 0) {
                chatBody.innerHTML = '<div class="empty-message">هنوز پیامی ارسال نشده است</div>';
                return;
            }
            
            // مرتب‌سازی پیام‌ها بر اساس زمان
            messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            // نمایش پیام‌ها
            messages.forEach(msg => {
                // اضافه کردن شناسه فرستنده پیام برای نمایش صحیح
                msg.sender_id = parseInt(msg.sender_id);
                displayGlobalMessage(msg);
            });
            
            // اسکرول به آخرین پیام
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight;
            }, 100);
            
            // علامت‌گذاری پیام‌های عمومی به عنوان خوانده‌شده
            markMessagesAsRead(null, true);
        })
        .catch(error => {
            console.error('Error fetching global chat history:', error);
            chatBody.innerHTML = '<div class="error-message">خطا در بارگذاری پیام‌ها. لطفا دوباره تلاش کنید.</div>';
        });
}

function sendMessage() {
    const messageInput = document.getElementById('chatMessage');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    if (currentTab === 'private' && currentChatUser) {
        // ارسال پیام خصوصی به سرور با استفاده از fetch
        fetch('/chat/api/chat/send/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                receiver_id: currentChatUser,
                message: message,
                is_global: false
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('خطا در ارسال پیام');
            }
            return response.json();
        })
        .then(data => {
            console.log('Message sent:', data);
            // نمایش پیام در صفحه چت
            displayPrivateMessage({
                sender_id: userId,
                receiver_id: currentChatUser,
                message: message,
                timestamp: data.timestamp || new Date().toISOString()
            });
            
            // پاک کردن فیلد پیام
            messageInput.value = '';
            
            // اسکرول به پایین صفحه چت
            const chatBody = document.getElementById('privateChatBody');
            chatBody.scrollTop = chatBody.scrollHeight;
        })
        .catch(error => {
            console.error('Error sending message:', error);
            alert('خطا در ارسال پیام. لطفا دوباره تلاش کنید.');
        });
    } 
    else if (currentTab === 'global') {
        // ارسال پیام عمومی به سرور
        fetch('/chat/api/chat/send/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                message: message,
                is_global: true
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('خطا در ارسال پیام');
            }
            return response.json();
        })
        .then(data => {
            console.log('Global message sent:', data);
            // نمایش پیام در صفحه چت عمومی
            displayGlobalMessage({
                sender_id: userId,
                username: username,
                message: message,
                timestamp: data.timestamp || new Date().toISOString()
            });
            
            // پاک کردن فیلد پیام
            messageInput.value = '';
            
            // اسکرول به پایین صفحه چت
            const chatBody = document.getElementById('globalChatBody');
            chatBody.scrollTop = chatBody.scrollHeight;
        })
        .catch(error => {
            console.error('Error sending global message:', error);
            alert('خطا در ارسال پیام. لطفا دوباره تلاش کنید.');
        });
    }
}

// ارسال فایل
function sendFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) return;
    
    // نمایش لودینگ
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'loading-message';
    loadingMessage.textContent = 'در حال آپلود فایل...';
    
    const chatBody = (currentTab === 'private') ? 
                      document.getElementById('privateChatBody') : 
                      document.getElementById('globalChatBody');
    
    chatBody.appendChild(loadingMessage);
    
    const formData = new FormData();
    formData.append('file', file);
    
    if (currentTab === 'private' && currentChatUser) {
        formData.append('receiver_id', currentChatUser);
        formData.append('is_global', 'false');
    } else if (currentTab === 'global') {
        formData.append('is_global', 'true');
    } else {
        loadingMessage.remove();
        alert('لطفاً ابتدا یک کاربر یا چت عمومی را انتخاب کنید');
        return;
    }
    
    // آپلود فایل به سرور
    fetch('/chat/api/chat/upload/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('خطا در آپلود فایل: ' + response.statusText);
        }
        return response.json();
    })
    .then(data => {
        // حذف پیام لودینگ
        loadingMessage.remove();
        
        // پاک کردن فیلد فایل
        fileInput.value = '';
        
        if (data.success) {
            // فایل با موفقیت آپلود شد
            console.log('File uploaded successfully:', data);
            
            if (currentTab === 'private') {
                displayPrivateMessage({
                    sender_id: userId,
                    receiver_id: currentChatUser,
                    file_url: data.file_url,
                    file_type: data.file_type,
                    timestamp: data.timestamp
                });
            } else {
                displayGlobalMessage({
                    sender_id: userId,
                    username: username,
                    file_url: data.file_url,
                    file_type: data.file_type,
                    timestamp: data.timestamp
                });
            }
            
            // اسکرول به پایین صفحه چت
            chatBody.scrollTop = chatBody.scrollHeight;
        } else {
            // خطا در آپلود فایل
            console.error('Error uploading file:', data.error);
            alert('خطا در آپلود فایل: ' + (data.error || 'خطای ناشناخته'));
        }
    })
    .catch(error => {
        // حذف پیام لودینگ
        loadingMessage.remove();
        
        // پاک کردن فیلد فایل
        fileInput.value = '';
        
        console.error('Error uploading file:', error);
        alert('خطا در آپلود فایل: ' + error.message);
    });
}

// توابع مرتبط با رابط کاربری چت
function toggleChat() {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.classList.toggle('active');
    
    if (chatContainer.classList.contains('active')) {
        // هنگام فعال کردن چت، داده‌ها را بارگذاری می‌کنیم
        loadUserList();
        if (currentTab === 'global') {
            loadGlobalChatHistory();
        } else if (currentChatUser) {
            loadChatHistory();
        }
    }
}

function toggleUserList() {
    console.log('Toggling user list');
    const userList = document.getElementById('userList');
    const isActive = userList.classList.contains('active');
    
    // اگر لیست فعال نیست، ابتدا دیتای کاربران را بارگذاری کنیم
    if (!isActive) {
        loadUserList();
    }
    
    // تغییر وضعیت نمایش لیست
    userList.classList.toggle('active');
    
    console.log('User list toggled:', userList.classList.contains('active'));
}

function switchTab(tab) {
    currentTab = tab;
    localStorage.setItem('currentChatTab', tab);
    
    const privateChatTab = document.getElementById('privateTabBtn');
    const globalChatTab = document.getElementById('globalTabBtn');
    const privateChatBody = document.getElementById('privateChatBody');
    const globalChatBody = document.getElementById('globalChatBody');
    
    // استفاده از chatTitle به جای .chat-header span
    const chatTitle = document.getElementById('chatTitle');
    
    privateChatTab.classList.remove('active');
    globalChatTab.classList.remove('active');
    privateChatBody.style.display = 'none';
    globalChatBody.style.display = 'none';
    
    if (tab === 'private') {
        privateChatTab.classList.add('active');
        privateChatBody.style.display = 'flex';
        
        // نشان دادن نام کاربر در سربرگ چت
        if (currentChatUser) {
            const username = localStorage.getItem('currentChatUsername') || 'کاربر';
            if (chatTitle) {
                chatTitle.textContent = `چت با ${username}`;
            }
            loadChatHistory();
            
            // حذف نشانگر پیام جدید
            resetBadge('private', currentChatUser);
            
            // علامت‌گذاری پیام‌ها به عنوان خوانده‌شده
            markMessagesAsRead(currentChatUser);
            
            // برای موبایل: نمایش صفحه چت به جای لیست کاربران
            if (window.innerWidth <= 768) {
                const userList = document.getElementById('userList');
                const chatBox = document.getElementById('chatBox');
                userList.classList.remove('active');
                chatBox.classList.add('active');
            }
        } else {
            if (chatTitle) {
                chatTitle.textContent = 'لطفاً یک کاربر انتخاب کنید';
            }
            privateChatBody.innerHTML = '<div class="empty-message">لطفاً از لیست، یک کاربر را برای چت انتخاب کنید</div>';
        }
    } else if (tab === 'global') {
        globalChatTab.classList.add('active');
        globalChatBody.style.display = 'flex';
        if (chatTitle) {
            chatTitle.textContent = 'چت عمومی';
        }
        
        loadGlobalChatHistory();
        
        // حذف نشانگر پیام جدید
        resetBadge('global');
        
        // علامت‌گذاری پیام‌های عمومی به عنوان خوانده‌شده
        markMessagesAsRead(null, true);
    }
}

function resetBadge(type, userId = null) {
    // حذف نشانگر پیام جدید
    if (type === 'private' && userId) {
        // برای پیام‌های خصوصی
        userNewMessages[userId] = 0;
        localStorage.setItem('userNewMessages', JSON.stringify(userNewMessages));
        
        // حذف نشانگر از لیست کاربران
        const userItem = document.querySelector(`.user-item[data-user-id="${userId}"]`);
        if (userItem) {
            userItem.classList.remove('has-new-message');
            const badge = userItem.querySelector('.chat-badge');
            if (badge) {
                badge.style.display = 'none';
            }
        }
    } else if (type === 'global') {
        // برای پیام‌های عمومی
        globalNewMessages = 0;
        localStorage.setItem('globalNewMessages', globalNewMessages.toString());
        
        // حذف نشانگر از تب چت عمومی
        const globalTab = document.getElementById('globalTabBtn');
        const globalBadge = globalTab.querySelector('.chat-badge');
        if (globalBadge) {
            globalBadge.style.display = 'none';
        }
    }
}

function markMessagesAsRead(userId = null, isGlobal = false) {
    // فرستادن درخواست به سرور برای علامت‌گذاری پیام‌ها به عنوان خوانده‌شده
    const url = isGlobal ? '/chat/api/chat/mark-as-read/?is_global=true' : `/chat/api/chat/mark-as-read/?sender_id=${userId}`;
    
    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            console.error('خطا در علامت‌گذاری پیام‌ها به عنوان خوانده‌شده');
        }
    })
    .catch(error => {
        console.error('خطا در ارسال درخواست علامت‌گذاری پیام‌ها:', error);
    });
}

// تابع دریافت مقدار کوکی برای CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// نمایش پیام خصوصی
function displayPrivateMessage(msg) {
    const chatBody = document.getElementById('privateChatBody');
    
    // اطمینان از وجود timestamp
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    // تولید id یکتا برای این پیام
    const messageId = `private-${msg.sender_id}-${Date.now()}`;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${msg.sender_id == userId ? 'sent' : 'received'}`;
    messageDiv.id = messageId;
    
    if (msg.message) {
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = msg.message;
        messageDiv.appendChild(messageContent);
    } else if (msg.file_url) {
        if (msg.file_type && msg.file_type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = msg.file_url;
            img.loading = 'lazy';
            img.alt = 'تصویر ارسالی';
            img.onclick = function() {
                window.open(msg.file_url, '_blank');
            };
            messageDiv.appendChild(img);
        } else {
            const link = document.createElement('a');
            link.href = msg.file_url;
            link.textContent = 'دانلود فایل';
            link.download = '';
            link.target = '_blank';
            messageDiv.appendChild(link);
        }
    }
    
    // اضافه کردن زمان
    if (msg.timestamp) {
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'chat-timestamp';
        timestampDiv.textContent = formatDateTime(msg.timestamp);
        messageDiv.appendChild(timestampDiv);
    }
    
    // حذف پیام‌های "خالی" یا "در حال بارگذاری" اگر وجود دارند
    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(msg => msg.remove());
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// نمایش پیام عمومی
function displayGlobalMessage(msg) {
    const chatBody = document.getElementById('globalChatBody');
    
    // اطمینان از وجود timestamp
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    // تولید id یکتا برای این پیام
    const messageId = `global-${msg.sender_id}-${Date.now()}`;
    
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    
    // مشخص کردن اینکه پیام از خود کاربر است یا از دیگران
    if (msg.sender_id == userId) {
        messageDiv.className = 'chat-message sent';
    } else {
        messageDiv.className = 'chat-message global';
        
        // اضافه کردن نام فرستنده به پیام
        if (msg.username) {
            const senderName = document.createElement('div');
            senderName.className = 'sender-name';
            senderName.textContent = msg.username;
            messageDiv.appendChild(senderName);
        }
    }
    
    if (msg.message) {
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = msg.message;
        messageDiv.appendChild(messageContent);
    } else if (msg.file_url) {
        if (msg.file_type && msg.file_type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = msg.file_url;
            img.loading = 'lazy';
            img.alt = 'تصویر ارسالی';
            img.onclick = function() {
                window.open(msg.file_url, '_blank');
            };
            messageDiv.appendChild(img);
        } else {
            const link = document.createElement('a');
            link.href = msg.file_url;
            link.textContent = 'دانلود فایل';
            link.download = '';
            link.target = '_blank';
            messageDiv.appendChild(link);
        }
    }
    
    // اضافه کردن زمان
    if (msg.timestamp) {
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'chat-timestamp';
        timestampDiv.textContent = formatDateTime(msg.timestamp);
        messageDiv.appendChild(timestampDiv);
    }
    
    // حذف پیام‌های "خالی" یا "در حال بارگذاری" اگر وجود دارند
    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(msg => msg.remove());
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// تابع تبدیل تاریخ به فرمت نمایشی مناسب
function formatDateTime(dateString) {
    try {
        const date = new Date(dateString);
        // تبدیل تاریخ به شمسی (با استفاده از PersianDate)
        if (typeof persianDate !== 'undefined') {
            const pDate = new persianDate(date);
            const jDate = pDate.format('YYYY/MM/DD');
            const time = date.toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit'});
            return `${jDate} ${time}`;
        } else {
            // اگر کتابخانه persianDate در دسترس نبود، فرمت استاندارد را برگردان
            return date.toLocaleDateString('fa-IR') + ' ' + 
                   date.toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit'});
        }
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateString; // در صورت خطا همان مقدار اصلی را برگردان
    }
} 