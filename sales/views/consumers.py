from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from chat.MessageModel import Message

class TaskConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("tasks", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("tasks", self.channel_name)

    async def task_update(self, event):
        await self.send(text_data=json.dumps(event))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_name = f"chat_{self.user_id}"
        
        # اضافه کردن کاربر به گروه پیام‌خصوصی
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        
        # اضافه کردن کاربر به گروه چت عمومی
        await self.channel_layer.group_add(
            'global_chat',
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        # حذف کاربر از گروه پیام‌خصوصی
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )
        
        # حذف کاربر از گروه چت عمومی
        await self.channel_layer.group_discard(
            'global_chat',
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            message = data.get('message')
            receiver_id = data.get('receiver_id')
            
            # ذخیره پیام در دیتابیس
            await self.save_message(message=message, receiver_id=receiver_id)
            
            # ارسال به گیرنده شخصی
            await self.channel_layer.group_send(
                f"chat_{receiver_id}",
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': int(self.user_id),
                    'receiver_id': int(receiver_id)
                }
            )
        
        elif message_type == 'file_message':
            file_url = data.get('file_url')
            file_type = data.get('file_type')
            receiver_id = data.get('receiver_id')
            
            # ذخیره فایل در دیتابیس
            await self.save_file(file_url=file_url, file_type=file_type, receiver_id=receiver_id)
            
            # ارسال به گیرنده شخصی
            await self.channel_layer.group_send(
                f"chat_{receiver_id}",
                {
                    'type': 'file_message',
                    'file_url': file_url,
                    'file_type': file_type,
                    'sender_id': int(self.user_id),
                    'receiver_id': int(receiver_id)
                }
            )
        
        elif message_type == 'global_message':
            message = data.get('message')
            
            # ذخیره پیام عمومی
            await self.save_global_message(message)
            
            # ارسال به همه در گروه چت عمومی
            await self.channel_layer.group_send(
                'global_chat',
                {
                    'type': 'global_message',
                    'message': message,
                    'sender_id': int(self.user_id)
                }
            )
            
        elif message_type == 'global_file_message':
            file_url = data.get('file_url')
            file_type = data.get('file_type')
            
            # ذخیره فایل عمومی
            await self.save_global_file(file_url=file_url, file_type=file_type)
            
            # ارسال به همه در گروه چت عمومی
            await self.channel_layer.group_send(
                'global_chat',
                {
                    'type': 'global_file_message',
                    'file_url': file_url,
                    'file_type': file_type,
                    'sender_id': int(self.user_id)
                }
            )
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def file_message(self, event):
        await self.send(text_data=json.dumps(event))
    
    async def global_message(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def global_file_message(self, event):
        await self.send(text_data=json.dumps(event))
    
    @database_sync_to_async
    def save_message(self, message, receiver_id):
        sender = User.objects.get(id=self.user_id)
        receiver = User.objects.get(id=receiver_id)
        Message.objects.create(
            sender=sender,
            receiver=receiver,
            message=message
        )
    
    @database_sync_to_async
    def save_file(self, file_url, file_type, receiver_id):
        sender = User.objects.get(id=self.user_id)
        receiver = User.objects.get(id=receiver_id)
        Message.objects.create(
            sender=sender,
            receiver=receiver,
            file_url=file_url,
            file_type=file_type
        )
    
    @database_sync_to_async
    def save_global_message(self, message):
        sender = User.objects.get(id=self.user_id)
        Message.objects.create(
            sender=sender,
            receiver=sender,  # برای سادگی، خود فرستنده را گیرنده قرار می‌دهیم
            message=message,
            is_global=True
        )
        
    @database_sync_to_async
    def save_global_file(self, file_url, file_type):
        sender = User.objects.get(id=self.user_id)
        Message.objects.create(
            sender=sender,
            receiver=sender,  # برای سادگی، خود فرستنده را گیرنده قرار می‌دهیم
            file_url=file_url,
            file_type=file_type,
            is_global=True
        )