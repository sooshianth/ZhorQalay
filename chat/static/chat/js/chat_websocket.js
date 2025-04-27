function displayPrivateMessage(msg) {
    const chatBody = document.getElementById('privateChatBody');
    
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    const messageId = msg.id ? `msg-${msg.id}` : `private-${msg.sender_id}-${Date.now()}`;
    if (document.getElementById(messageId)) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${msg.sender_id == userId ? 'sent' : 'received'}`;
    messageDiv.id = messageId;
    
    if (msg.reply_to && msg.reply_to_message) {
        const replyDiv = document.createElement('div');
        replyDiv.className = 'reply-preview';
        replyDiv.innerHTML = `
            <a href="#" class="reply-link" onclick="scrollToMessage('msg-${msg.reply_to}');return false;">
                <span class="reply-author">${msg.reply_to_author || 'کاربر'}:</span>
                <span class="reply-text">${msg.reply_to_message.substring(0, 40)}${msg.reply_to_message.length > 40 ? '...' : ''}</span>
            </a>
        `;
        messageDiv.appendChild(replyDiv);
    }
    
    if (msg.message) {
        const messageContent = document.createElement('div');
        messageContent.textContent = msg.message;
        messageDiv.appendChild(messageContent);
    } else if (msg.file_url) {
        if (msg.file_type && msg.file_type.startsWith('image/')) {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'image-container';
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'loading-spinner';
            loadingSpinner.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            imgContainer.appendChild(loadingSpinner);
            
            const img = document.createElement('img');
            img.style.display = 'none';
            img.alt = 'تصویر';
            img.onload = function() {
                loadingSpinner.remove();
                img.style.display = 'block';
            };
            img.onerror = function() {
                loadingSpinner.remove();
                imgContainer.innerHTML = '<div class="error-message">خطا در بارگذاری تصویر</div>';
            };
            img.src = msg.file_url;
            imgContainer.appendChild(img);
            messageDiv.appendChild(imgContainer);
            img.onclick = function() {
                window.open(msg.file_url, '_blank');
            };
        } else {
            const fileLink = document.createElement('a');
            fileLink.href = msg.file_url;
            fileLink.download = '';
            fileLink.target = '_blank';
            fileLink.className = 'file-link';
            let fileIcon = 'fa-file';
            let fileType = 'فایل';
            if (msg.file_type) {
                if (msg.file_type.includes('pdf')) {
                    fileIcon = 'fa-file-pdf';
                    fileType = 'PDF';
                } else if (msg.file_type.includes('word') || msg.file_type.includes('doc')) {
                    fileIcon = 'fa-file-word';
                    fileType = 'Word';
                } else if (msg.file_type.includes('excel') || msg.file_type.includes('sheet')) {
                    fileIcon = 'fa-file-excel';
                    fileType = 'Excel';
                } else if (msg.file_type.includes('video')) {
                    fileIcon = 'fa-file-video';
                    fileType = 'ویدیو';
                } else if (msg.file_type.includes('audio')) {
                    fileIcon = 'fa-file-audio';
                    fileType = 'صوت';
                } else if (msg.file_type.includes('zip') || msg.file_type.includes('rar')) {
                    fileIcon = 'fa-file-archive';
                    fileType = 'فایل فشرده';
                }
            }
            fileLink.innerHTML = `<i class="fas ${fileIcon}"></i> دانلود ${fileType}`;
            messageDiv.appendChild(fileLink);
        }
    }
    
    if (msg.timestamp) {
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'chat-timestamp';
        timestampDiv.textContent = formatDateTime(msg.timestamp);
        messageDiv.appendChild(timestampDiv);
    }
    
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'message-actions';
    
    const replyBtn = document.createElement('button');
    replyBtn.className = 'reply-btn';
    replyBtn.title = 'ریپلای';
    replyBtn.innerHTML = '<i class="fas fa-reply"></i>';
    replyBtn.onclick = function() { setReplyTo(msg); };
    
    const pinBtn = document.createElement('button');
    pinBtn.className = 'pin-btn';
    pinBtn.title = msg.is_pinned ? 'برداشتن پین' : 'پین کردن';
    pinBtn.innerHTML = `<i class="fas fa-thumbtack${msg.is_pinned ? ' pinned' : ''}"></i>`;
    pinBtn.onclick = function() { 
        if (msg.is_pinned) {
            unpinMessage(msg);
        } else {
            pinMessage(msg);
        }
    };
    
    actionsDiv.appendChild(replyBtn);
    actionsDiv.appendChild(pinBtn);
    messageDiv.appendChild(actionsDiv);
    
    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(element => {
        if (!element.closest('.chat-message')) {
            element.remove();
        }
    });
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function displayGlobalMessage(msg) {
    const chatBody = document.getElementById('globalChatBody');
    
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    const messageId = msg.id ? `msg-${msg.id}` : `global-${msg.sender_id}-${Date.now()}`;
    if (document.getElementById(messageId)) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${msg.sender_id == userId ? 'sent' : 'global'}`;
    messageDiv.id = messageId;
    
    if (msg.reply_to && msg.reply_to_message) {
        const replyDiv = document.createElement('div');
        replyDiv.className = 'reply-preview';
        replyDiv.innerHTML = `
            <a href="#" class="reply-link" onclick="scrollToMessage('msg-${msg.reply_to}');return false;">
                <span class="reply-author">${msg.reply_to_author || 'کاربر'}:</span>
                <span class="reply-text">${msg.reply_to_message.substring(0, 40)}${msg.reply_to_message.length > 40 ? '...' : ''}</span>
            </a>
        `;
        messageDiv.appendChild(replyDiv);
    }
    
    if (msg.sender_id != userId) {
        const senderName = document.createElement('div');
        senderName.className = 'sender-name';
        senderName.textContent = msg.username || 'کاربر';
        messageDiv.appendChild(senderName);
    }
    
    if (msg.message) {
        const messageContent = document.createElement('div');
        messageContent.textContent = msg.message;
        messageDiv.appendChild(messageContent);
    } else if (msg.file_url) {
        if (msg.file_type && msg.file_type.startsWith('image/')) {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'image-container';
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'loading-spinner';
            loadingSpinner.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            imgContainer.appendChild(loadingSpinner);
            
            const img = document.createElement('img');
            img.style.display = 'none';
            img.alt = 'تصویر';
            img.onload = function() {
                loadingSpinner.remove();
                img.style.display = 'block';
            };
            img.onerror = function() {
                loadingSpinner.remove();
                imgContainer.innerHTML = '<div class="error-message">خطا در بارگذاری تصویر</div>';
            };
            img.src = msg.file_url;
            imgContainer.appendChild(img);
            messageDiv.appendChild(imgContainer);
            img.onclick = function() {
                window.open(msg.file_url, '_blank');
            };
        } else {
            const fileLink = document.createElement('a');
            fileLink.href = msg.file_url;
            fileLink.download = '';
            fileLink.target = '_blank';
            fileLink.className = 'file-link';
            let fileIcon = 'fa-file';
            let fileType = 'فایل';
            if (msg.file_type) {
                if (msg.file_type.includes('pdf')) {
                    fileIcon = 'fa-file-pdf';
                    fileType = 'PDF';
                } else if (msg.file_type.includes('word') || msg.file_type.includes('doc')) {
                    fileIcon = 'fa-file-word';
                    fileType = 'Word';
                } else if (msg.file_type.includes('excel') || msg.file_type.includes('sheet')) {
                    fileIcon = 'fa-file-excel';
                    fileType = 'Excel';
                } else if (msg.file_type.includes('video')) {
                    fileIcon = 'fa-file-video';
                    fileType = 'ویدیو';
                } else if (msg.file_type.includes('audio')) {
                    fileIcon = 'fa-file-audio';
                    fileType = 'صوت';
                } else if (msg.file_type.includes('zip') || msg.file_type.includes('rar')) {
                    fileIcon = 'fa-file-archive';
                    fileType = 'فایل فشرده';
                }
            }
            fileLink.innerHTML = `<i class="fas ${fileIcon}"></i> دانلود ${fileType}`;
            messageDiv.appendChild(fileLink);
        }
    }
    
    if (msg.timestamp) {
        const timestampDiv = document.createElement('div');
        timestampDiv.className = 'chat-timestamp';
        timestampDiv.textContent = formatDateTime(msg.timestamp);
        messageDiv.appendChild(timestampDiv);
    }
    
    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'message-actions';
    
    const replyBtn = document.createElement('button');
    replyBtn.className = 'reply-btn';
    replyBtn.title = 'ریپلای';
    replyBtn.innerHTML = '<i class="fas fa-reply"></i>';
    replyBtn.onclick = function() { setReplyTo(msg); };
    
    const pinBtn = document.createElement('button');
    pinBtn.className = 'pin-btn';
    pinBtn.title = msg.is_pinned ? 'برداشتن پین' : 'پین کردن';
    pinBtn.innerHTML = `<i class="fas fa-thumbtack${msg.is_pinned ? ' pinned' : ''}"></i>`;
    pinBtn.onclick = function() { 
        if (msg.is_pinned) {
            unpinMessage(msg);
        } else {
            pinMessage(msg);
        }
    };
    
    actionsDiv.appendChild(replyBtn);
    actionsDiv.appendChild(pinBtn);
    messageDiv.appendChild(actionsDiv);
    
    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(element => {
        if (!element.closest('.chat-message')) {
            element.remove();
        }
    });
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

// ارسال فایل
function sendFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) return;
    
    // یک timestamp برای فایل جدید ایجاد کنیم
    const now = new Date();
    const timestamp = now.toISOString();
    
    // نمایش پیام لودینگ
    const chatBody = (currentTab === 'private') ? 
        document.getElementById('privateChatBody') : 
        document.getElementById('globalChatBody');
    
    // افزودن پیام لودینگ به صورت موقت
    const loadingId = `loading-${Date.now()}`;
    const loadingDiv = document.createElement('div');
    loadingDiv.id = loadingId;
    loadingDiv.className = 'chat-message sent';
    loadingDiv.innerHTML = '<div class="loading-message">در حال ارسال فایل...</div>';
    chatBody.appendChild(loadingDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
    
    const formData = new FormData();
    formData.append('file', file);
    
    if (currentTab === 'private' && currentChatUser) {
        formData.append('receiver_id', currentChatUser);
        formData.append('is_global', 'false');
    } else if (currentTab === 'global') {
        formData.append('is_global', 'true');
    } else {
        // حذف پیام لودینگ در صورت خطا
        document.getElementById(loadingId)?.remove();
        console.log('Invalid context for file upload');
        return;
    }

    fetch('/chat/api/chat/upload/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include',
        body: formData
    })
    .then(response => {
        console.log('File Upload Response Status:', response.status);
        if (!response.ok) {
            throw new Error('Failed to upload file: ' + response.statusText);
        }
        return response.json();
    })
    .then(data => {
        console.log('File Upload Response:', data);
        
        // حذف پیام لودینگ
        document.getElementById(loadingId)?.remove();
        
        if (data.file_url) {
            // نمایش فایل آپلود شده در UI بدون وابستگی به WebSocket
            if (currentTab === 'private' && currentChatUser) {
                const messageData = {
                    sender_id: userId,
                    receiver_id: currentChatUser,
                    file_url: data.file_url,
                    file_type: data.file_type || file.type,
                    timestamp: data.timestamp || timestamp
                };
                
                // نمایش پیام در UI
                displayPrivateMessage(messageData);
                
                // ارسال پیام به سرور از طریق WebSocket اگر متصل باشد
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    chatSocket.send(JSON.stringify({
                        'type': 'file_message',
                        'file_url': data.file_url,
                        'receiver_id': currentChatUser,
                        'file_type': file.type,
                        'timestamp': timestamp
                    }));
                }
            }
            else if (currentTab === 'global') {
                const messageData = {
                    sender_id: userId,
                    username: username,
                    file_url: data.file_url,
                    file_type: data.file_type || file.type,
                    timestamp: data.timestamp || timestamp
                };
                
                // نمایش پیام در UI
                displayGlobalMessage(messageData);
                
                // ارسال پیام به سرور از طریق WebSocket اگر متصل باشد
                if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
                    chatSocket.send(JSON.stringify({
                        'type': 'global_file_message',
                        'file_url': data.file_url,
                        'file_type': file.type,
                        'timestamp': timestamp
                    }));
                }
            }
        } else {
            console.error('No file URL in response:', data);
            alert('خطا در ارسال فایل: آدرس فایل دریافت نشد');
        }
    })
    .catch(error => {
        // حذف پیام لودینگ در صورت خطا
        document.getElementById(loadingId)?.remove();
        
        console.error('Error uploading file:', error);
        alert('خطا در آپلود فایل: ' + error.message);
    });
    
    fileInput.value = '';
}

// علامت‌گذاری پیام‌ها به عنوان خوانده‌شده
function markMessagesAsRead(senderId = null, isGlobal = false) {
    const data = new FormData();
    
    if (isGlobal) {
        data.append('is_global', 'true');
    } else if (senderId) {
        data.append('sender_id', senderId);
    } else {
        console.error('Either senderId or isGlobal must be provided');
        return;
    }
    
    fetch('/chat/api/chat/mark-as-read/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        },
        credentials: 'include',
        body: data
    })
    .then(response => response.json())
    .then(data => {
        console.log('Messages marked as read:', data);
        
        // پس از علامت‌گذاری پیام‌ها، وضعیت را بروزرسانی کنیم
        if (isGlobal) {
            newGlobalMessages = 0;
            newTotalMessages = newPrivateMessages;
        } else if (senderId) {
            if (userNewMessages[senderId]) {
                newTotalMessages -= userNewMessages[senderId];
                newPrivateMessages -= userNewMessages[senderId];
                userNewMessages[senderId] = 0;
            }
        }
        
        // بروزرسانی نشانگرها
        saveNewMessageState();
        updateBadges();
    })
    .catch(error => {
        console.error('Error marking messages as read:', error);
    });
}

// راه‌اندازی وب‌سوکت
function initChatWebSocket(userIdParam, usernameParam) {
    // ذخیره شناسه کاربر و نام کاربری در متغیرهای سراسری
    userId = userIdParam;
    username = usernameParam;
    
    // بازیابی وضعیت پیام‌های جدید از localStorage
    loadNewMessageState();
    
    // بررسی پیام‌های جدید از سرور
    setTimeout(checkForNewMessages, 1000);
    
    // ایجاد اتصال وب‌سوکت
    chatSocket = new WebSocket(`ws://${window.location.host}/ws/chat/${userId}/`);
    
    chatSocket.onopen = function() {
        console.log('WebSocket چت متصل شد');
        
        // بروزرسانی نشانگرها هنگام اتصال به سرور
        setTimeout(updateBadges, 300);
    };

    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        console.log('WebSocket message received:', data);
        
        // پنجره چت باز است یا نه
        const isChatWindowOpen = document.getElementById('chatWindow').style.display === 'flex';
        
        if (data.type === 'chat_message' || data.type === 'file_message') {
            // اگر پیام خصوصی است
            const isCurrentChat = currentChatUser && (data.sender_id === currentChatUser || data.receiver_id === currentChatUser);
            const isActiveTab = currentTab === 'private';
            const shouldShowNotification = !isChatWindowOpen || !isCurrentChat || !isActiveTab;
            
            if (data.sender_id !== userId) {
                // برای پیام‌های دریافتی
                if (shouldShowNotification) {
                    // شمارش پیام‌های جدید خصوصی
                    newTotalMessages++;
                    newPrivateMessages++;
                    
                    // ذخیره اطلاعات فرستنده
                    const senderId = data.sender_id.toString();
                    if (!userNewMessages[senderId]) {
                        userNewMessages[senderId] = 0;
                    }
                    userNewMessages[senderId]++;
                    
                    // ذخیره و بروزرسانی نشانگرها
                    saveNewMessageState();
                    updateBadges();
                    
                    // دریافت نام کاربر فرستنده
                    fetchSenderName(data.sender_id).then(senderName => {
                        // نمایش نوتیفیکیشن
                        showNewMessageNotification(data.message || 'فایل جدید', senderName);
                    });
                }
            }
            
            if (isCurrentChat) {
                displayPrivateMessage(data);
                
                // اگر پیام از طرف کاربر دیگر است و چت فعال و باز است، پیام را خوانده شده در نظر بگیر
                if (data.sender_id !== userId && isChatWindowOpen && isActiveTab) {
                    markMessagesAsRead(data.sender_id);
                }
            }
        } 
        else if (data.type === 'global_message' || data.type === 'global_file_message') {
            // اگر پیام عمومی است
            const isActiveTab = currentTab === 'global' && isChatWindowOpen;
            const shouldShowNotification = !isActiveTab;
            
            // ایجاد یک شناسه یکتا برای این پیام
            const messageId = `${data.sender_id}-${data.timestamp}`;
            
            // فقط نشانگر برای پیام‌های دیگران نمایش داده شود
            if (data.sender_id !== userId) {
                if (shouldShowNotification) {
                    // شمارش پیام‌های جدید عمومی
                    newTotalMessages++;
                    newGlobalMessages++;
                    
                    // ذخیره و بروزرسانی نشانگرها
                    saveNewMessageState();
                    updateBadges();
                    
                    // نمایش نوتیفیکیشن برای پیام عمومی
                    showNewMessageNotification(
                        data.message || 'فایل جدید', 
                        data.username || 'کاربر', 
                        true
                    );
                }
            }
            
            // بررسی تکراری نبودن پیام
            if (!document.getElementById(messageId)) {
                // نمایش پیام در صفحه چت عمومی
                data.username = data.sender_id === userId ? username : data.username;
                displayGlobalMessage(data);
                
                // اگر پیام از طرف کاربر دیگر است و چت عمومی فعال و باز است، پیام را خوانده شده در نظر بگیر
                if (data.sender_id !== userId && isActiveTab) {
                    markMessagesAsRead(null, true);
                }
            } else {
                console.log('Duplicate global message, skipping:', messageId);
            }
        }
    };

    chatSocket.onclose = function(e) {
        console.error('WebSocket چت بسته شد:', e);
        
        // تلاش مجدد برای اتصال بعد از 5 ثانیه
        setTimeout(() => {
            chatSocket = new WebSocket(`ws://${window.location.host}/ws/chat/${userId}/`);
        }, 5000);
    };

    chatSocket.onerror = function(e) {
        console.error('WebSocket خطا:', e);
    };
}

// دریافت نام کاربر با شناسه
function fetchSenderName(senderId) {
    return fetch(`/chat/api/username/${senderId}/`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('خطا در دریافت نام کاربر');
        }
        return response.json();
    })
    .then(data => {
        if (data.username) {
            return data.username;
        }
        return 'کاربر';
    })
    .catch(error => {
        console.error('Error fetching sender name:', error);
        return 'کاربر';
    });
}

// بررسی پیام‌های جدید از سرور
function checkForNewMessages() {
    // بررسی پیام‌های خصوصی جدید
    fetch('/chat/api/chat/unread/count/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('خطا در دریافت پیام‌های جدید');
        }
        return response.json();
    })
    .then(data => {
        if (data.count) {
            newPrivateMessages = data.count;
            userNewMessages = data.by_user || {};
        }
        
        // بررسی پیام‌های عمومی جدید
        return fetch('/chat/api/chat/global/unread/count/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'include'
        });
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('خطا در دریافت پیام‌های عمومی جدید');
        }
        return response.json();
    })
    .then(data => {
        if (data.count) {
            newGlobalMessages = data.count;
        }
        
        // محاسبه کل پیام‌های جدید
        newTotalMessages = newPrivateMessages + newGlobalMessages;
        
        // بروزرسانی نشانگرها
        saveNewMessageState();
        updateBadges();
    })
    .catch(error => {
        console.error('Error checking for new messages:', error);
    });
}

// اطمینان از نمایش نشانگرهای پیام‌های جدید پس از بارگذاری
function ensureBadges() {
    if (typeof updateBadges === 'function') {
        updateBadges();
    } else {
        setTimeout(ensureBadges, 500);
    }
} 

function pinMessage(msg) {
    fetch(`/chat/api/chat/pin/${msg.id}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showPinnedMessage(msg);
        }
    });
}

function showPinnedMessage(msg) {
    let pinBox = document.getElementById('pinBox');
    if (!pinBox) {
        pinBox = document.createElement('div');
        pinBox.id = 'pinBox';
        pinBox.className = 'pin-box';
        const chatBody = document.querySelector('.chat-body');
        chatBody.parentNode.insertBefore(pinBox, chatBody);
    }
    pinBox.innerHTML = `<i class="fas fa-thumbtack"></i> پیام پین شده: ${msg.message ? msg.message.substring(0, 50) : '[فایل]'}`;
}