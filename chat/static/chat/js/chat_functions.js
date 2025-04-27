function loadUserList() {
    console.log('Loading user list...');
    
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
                    
                    const userName = document.createElement('span');
                    userName.textContent = user.username;
                    userItem.appendChild(userName);
                    
                    const userStatus = document.createElement('span');
                    userStatus.className = 'user-status online';
                    userItem.appendChild(userStatus);
                    
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
            
            if (currentChatUser) {
                const activeUser = document.querySelector(`.user-item[data-user-id="${currentChatUser}"]`);
                if (activeUser) {
                    activeUser.classList.add('active');
                }
            }
        })
        .catch(error => {
            console.error('Error fetching users:', error);
            userListItems.innerHTML = '<div class="error-message">خطا در بارگذاری لیست کاربران: ' + error.message + '</div>';
        });
}

function startChat(userId, username) {
    switchTab('private');
    
    currentChatUser = userId;
    
    const chatTitle = document.getElementById('chatTitle');
    if (chatTitle) {
        chatTitle.textContent = `چت با ${username}`;
    }
    
    const userItems = document.querySelectorAll('.user-item');
    userItems.forEach(item => {
        item.classList.remove('active');
        if (parseInt(item.dataset.userId) === userId) {
            item.classList.add('active');
            item.classList.remove('has-new-message');
            const badge = item.querySelector('.chat-badge');
            if (badge) {
                badge.remove();
            }
        }
    });
    
    resetBadge('private', userId.toString());
    
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
            
            messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            messages.forEach(msg => {
                msg.sender_id = parseInt(msg.sender_id);
                msg.receiver_id = parseInt(msg.receiver_id);
                displayPrivateMessage(msg);
            });
            
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight;
            }, 100);
            
            markMessagesAsRead(currentChatUser);
            
            const pinnedMessage = messages.find(msg => msg.is_pinned);
            if (pinnedMessage) {
                showPinnedMessage(pinnedMessage);
            }
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
            
            messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            
            messages.forEach(msg => {
                msg.sender_id = parseInt(msg.sender_id);
                displayGlobalMessage(msg);
            });
            
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight;
            }, 100);
            
            markMessagesAsRead(null, true);
            
            const pinnedMessage = messages.find(msg => msg.is_pinned);
            if (pinnedMessage) {
                showPinnedMessage(pinnedMessage);
            }
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
        fetch('/chat/api/chat/send/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                receiver_id: currentChatUser,
                message: message,
                is_global: false,
                reply_to: replyToMessage ? replyToMessage.id : null
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
            displayPrivateMessage({
                id: data.message_id, 
                sender_id: userId,
                receiver_id: currentChatUser,
                message: message,
                timestamp: data.timestamp || new Date().toISOString(),
                reply_to: data.reply_to,
                reply_to_message: replyToMessage ? replyToMessage.message : null,
                reply_to_author: replyToMessage ? (replyToMessage.sender_id === userId ? username : null) : null
            });
            
            messageInput.value = '';
            clearReply();
            
            const chatBody = document.getElementById('privateChatBody');
            chatBody.scrollTop = chatBody.scrollHeight;
        })
        .catch(error => {
            console.error('Error sending message:', error);
            alert('خطا در ارسال پیام. لطفا دوباره تلاش کنید.');
        });
    } 
    else if (currentTab === 'global') {
        fetch('/chat/api/chat/send/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                message: message,
                is_global: true,
                reply_to: replyToMessage ? replyToMessage.id : null
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
            displayGlobalMessage({
                id: data.message_id, 
                sender_id: userId,
                username: username,
                message: message,
                timestamp: data.timestamp || new Date().toISOString(),
                reply_to: data.reply_to,
                reply_to_message: replyToMessage ? replyToMessage.message : null,
                reply_to_author: replyToMessage ? (replyToMessage.sender_id === userId ? username : null) : null
            });
            
            messageInput.value = '';
            clearReply();
            
            const chatBody = document.getElementById('globalChatBody');
            chatBody.scrollTop = chatBody.scrollHeight;
        })
        .catch(error => {
            console.error('Error sending global message:', error);
            alert('خطا در ارسال پیام. لطفا دوباره تلاش کنید.');
        });
    }
}

function sendFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) return;
    
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
        if (replyToMessage) {
            formData.append('reply_to', replyToMessage.id);
        }
    } else if (currentTab === 'global') {
        formData.append('is_global', 'true');
        if (replyToMessage) {
            formData.append('reply_to', replyToMessage.id);
        }
    } else {
        loadingMessage.remove();
        alert('لطفاً ابتدا یک کاربر یا چت عمومی را انتخاب کنید');
        return;
    }
    
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
        loadingMessage.remove();
        fileInput.value = '';
        
        if (data.success) {
            console.log('File uploaded successfully:', data);
            
            if (currentTab === 'private') {
                displayPrivateMessage({
                    sender_id: userId,
                    receiver_id: currentChatUser,
                    file_url: data.file_url,
                    file_type: data.file_type,
                    timestamp: data.timestamp,
                    reply_to: data.reply_to,
                    reply_to_message: replyToMessage ? replyToMessage.message : null,
                    reply_to_author: replyToMessage ? (replyToMessage.sender_id === userId ? username : null) : null
                });
            } else {
                displayGlobalMessage({
                    sender_id: userId,
                    username: username,
                    file_url: data.file_url,
                    file_type: data.file_type,
                    timestamp: data.timestamp,
                    reply_to: data.reply_to,
                    reply_to_message: replyToMessage ? replyToMessage.message : null,
                    reply_to_author: replyToMessage ? (replyToMessage.sender_id === userId ? username : null) : null
                });
            }
            
            clearReply();
            chatBody.scrollTop = chatBody.scrollHeight;
        } else {
            console.error('Error uploading file:', data.error);
            alert('خطا در آپلود فایل: ' + (data.error || 'خطای ناشناخته'));
        }
    })
    .catch(error => {
        loadingMessage.remove();
        fileInput.value = '';
        console.error('Error uploading file:', error);
        alert('خطا در آپلود فایل: ' + error.message);
    });
}

function toggleChat() {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.classList.toggle('active');
    
    if (chatContainer.classList.contains('active')) {
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
    
    if (!isActive) {
        loadUserList();
    }
    
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
    
    const chatTitle = document.getElementById('chatTitle');
    
    privateChatTab.classList.remove('active');
    globalChatTab.classList.remove('active');
    privateChatBody.style.display = 'none';
    globalChatBody.style.display = 'none';
    
    if (tab === 'private') {
        privateChatTab.classList.add('active');
        privateChatBody.style.display = 'flex';
        
        if (currentChatUser) {
            const username = localStorage.getItem('currentChatUsername') || 'کاربر';
            if (chatTitle) {
                chatTitle.textContent = `چت با ${username}`;
            }
            loadChatHistory();
            resetBadge('private', currentChatUser);
            markMessagesAsRead(currentChatUser);
            
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
        resetBadge('global');
        markMessagesAsRead(null, true);
    }
}

function resetBadge(type, userId = null) {
    if (type === 'private' && userId) {
        userNewMessages[userId] = 0;
        localStorage.setItem('userNewMessages', JSON.stringify(userNewMessages));
        
        const userItem = document.querySelector(`.user-item[data-user-id="${userId}"]`);
        if (userItem) {
            userItem.classList.remove('has-new-message');
            const badge = userItem.querySelector('.chat-badge');
            if (badge) {
                badge.style.display = 'none';
            }
        }
    } else if (type === 'global') {
        globalNewMessages = 0;
        localStorage.setItem('globalNewMessages', globalNewMessages.toString());
        
        const globalTab = document.getElementById('globalTabBtn');
        const globalBadge = globalTab.querySelector('.chat-badge');
        if (globalBadge) {
            globalBadge.style.display = 'none';
        }
    }
}

function markMessagesAsRead(userId = null, isGlobal = false) {
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

function displayPrivateMessage(msg) {
    const chatBody = document.getElementById('privateChatBody');
    
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    const messageId = msg.id ? `msg-${msg.id}` : `private-${msg.sender_id}-${Date.now()}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${msg.sender_id == userId ? 'sent' : 'received'}`;
    messageDiv.id = messageId;
    
    if (msg.reply_to && msg.reply_to_message) {
        const replyDiv = document.createElement('div');
        replyDiv.className = 'reply-preview';
        replyDiv.innerHTML = `
            <a href="#" class="reply-link" onclick="scrollToMessage('msg-${msg.reply_to}');return false;">
                <span class="reply-author">${msg.reply_to_author || 'کاربر'}:</span>
                <span class="reply-text">${msg.reply_to_message.substring(0, 40)}</span>
            </a>
        `;
        messageDiv.appendChild(replyDiv);
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
    pinBtn.title = 'پین کردن';
    pinBtn.innerHTML = '<i class="fas fa-thumbtack"></i>';
    pinBtn.onclick = function() { pinMessage(msg); };

    actionsDiv.appendChild(replyBtn);
    actionsDiv.appendChild(pinBtn);
    messageDiv.appendChild(actionsDiv);

    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(msg => msg.remove());

    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function displayGlobalMessage(msg) {
    const chatBody = document.getElementById('globalChatBody');
    
    if (!msg.timestamp) {
        msg.timestamp = new Date().toISOString();
    }
    
    const messageId = msg.id ? `msg-${msg.id}` : `global-${msg.sender_id}-${Date.now()}`;
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${msg.sender_id == userId ? 'sent' : 'global'}`;
    messageDiv.id = messageId;

    if (msg.reply_to && msg.reply_to_message) {
        const replyDiv = document.createElement('div');
        replyDiv.className = 'reply-preview';
        replyDiv.innerHTML = `
            <a href="#" class="reply-link" onclick="scrollToMessage('msg-${msg.reply_to}');return false;">
                <span class="reply-author">${msg.reply_to_author || 'کاربر'}:</span>
                <span class="reply-text">${msg.reply_to_message.substring(0, 40)}</span>
            </a>
        `;
        messageDiv.appendChild(replyDiv);
    }
    
    if (msg.sender_id != userId) {
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
    replyBtn.onclick = function() {
        setReplyTo(msg);
    };

    const pinBtn = document.createElement('button');
    pinBtn.className = 'pin-btn';
    pinBtn.title = 'پین کردن';
    pinBtn.innerHTML = '<i class="fas fa-thumbtack"></i>';
    pinBtn.onclick = function() {
        pinMessage(msg);
    };

    actionsDiv.appendChild(replyBtn);
    actionsDiv.appendChild(pinBtn);
    messageDiv.appendChild(actionsDiv);

    const emptyMessages = chatBody.querySelectorAll('.empty-message, .loading-message');
    emptyMessages.forEach(msg => msg.remove());
    
    chatBody.appendChild(messageDiv);
    chatBody.scrollTop = chatBody.scrollHeight;
}

function formatDateTime(dateString) {
    try {
        const date = new Date(dateString);
        if (typeof persianDate !== 'undefined') {
            const pDate = new persianDate(date);
            const jDate = pDate.format('YYYY/MM/DD');
            const time = date.toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit'});
            return `${jDate} ${time}`;
        } else {
            return date.toLocaleDateString('fa-IR') + ' ' + 
                   date.toLocaleTimeString('fa-IR', {hour: '2-digit', minute: '2-digit'});
        }
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateString;
    }
}

let replyToMessage = null;

function setReplyTo(msg) {
    replyToMessage = msg;
    const replyBox = document.getElementById('replyBox') || document.createElement('div');
    replyBox.id = 'replyBox';
    replyBox.className = 'reply-box';
    replyBox.innerHTML = `
        <span>در حال ریپلای به: ${msg.message ? msg.message.substring(0, 30) : '[فایل]'}</span>
        <button onclick="clearReply()" title="لغو ریپلای"><i class="fas fa-times"></i></button>
    `;
    const chatFooter = document.querySelector('.chat-footer');
    chatFooter.insertBefore(replyBox, chatFooter.firstChild);
}

function clearReply() {
    replyToMessage = null;
    const replyBox = document.getElementById('replyBox');
    if (replyBox) replyBox.remove();
}

function showPinnedMessage(msg) {
    const pinBox = document.getElementById('pinBox');
    const pinnedText = document.getElementById('pinnedMessageText');
    pinBox.style.display = 'flex';
    pinnedText.innerHTML = `<a href="#" onclick="scrollToMessage('msg-${msg.id}');return false;">${msg.message ? msg.message.substring(0, 50) : '[فایل]'}</a>`;
    pinBox.setAttribute('data-msg-id', msg.id);
}

function unpinPinnedMessage() {
    const pinBox = document.getElementById('pinBox');
    const messageId = pinBox.getAttribute('data-msg-id');
    if (messageId) {
        fetch(`/chat/api/chat/unpin/${messageId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                pinBox.style.display = 'none';
                pinBox.removeAttribute('data-msg-id');
            }
        });
    }
}

function scrollToMessage(messageId) {
    const target = document.getElementById(messageId);
    if (target) {
        target.classList.add('reply-highlight');
        target.scrollIntoView({behavior: 'smooth', block: 'center'});
        setTimeout(() => target.classList.remove('reply-highlight'), 1500);
    }
}

function pinMessage(msg) {
    if (!msg.id) {
        alert('شناسه پیام نامعتبر است');
        return;
    }
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