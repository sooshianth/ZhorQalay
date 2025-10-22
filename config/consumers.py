import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from chat.MessageModel import Message
import logging
import html
from core.logging_levels import *
logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            audit_logger.alert(f"Closing WebSocket for unauthenticated user")
            await self.close()
            return
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'chat_{self.user_id}'
        #print('Adding to group:', self.room_group_name)
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        #print('Disconnecting WebSocket, close code:', close_code)
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        #print('Received data:', data)
        receiver_id = data['receiver_id'] 
        #parse int
        receiver_id = str(int(receiver_id))
        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            audit_logger.activity(f"User with ID {receiver_id} does not exist")
            return

        if data['type'] == 'chat_message':
            message = html.escape(data['message'])
            try:
                msg = Message.objects.create(
                    sender=self.user,
                    receiver=receiver,
                    message=message
                )
                #print('Message saved:', msg)
            except Exception as e:
                logger.error(f"Error saving message: {str(e)}")
                return

            await self.channel_layer.group_send(
                f'chat_{receiver_id}',
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'receiver_id': receiver_id
                }
            )
            await self.channel_layer.group_send(
                f'chat_{self.user.id}',
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': self.user.id,
                    'receiver_id': receiver_id
                }
            )
        elif data['type'] == 'file_message':
            file_url = data['file_url']
            file_type = data['file_type']
            try:
                msg = Message.objects.create(
                    sender=self.user,
                    receiver=receiver,
                    file_url=file_url,
                    file_type=file_type
                )
                #print('File message saved:', msg)
            except Exception as e:
                logger.error(f"Error saving file message: {str(e)}")
                return

            await self.channel_layer.group_send(
                f'chat_{receiver_id}',
                {
                    'type': 'chat_message',
                    'file_url': file_url,
                    'file_type': file_type,
                    'sender_id': self.user.id,
                    'receiver_id': receiver_id
                }
            )
            await self.channel_layer.group_send(
                f'chat_{self.user.id}',
                {
                    'type': 'chat_message',
                    'file_url': file_url,
                    'file_type': file_type,
                    'sender_id': self.user.id,
                    'receiver_id': receiver_id
                }
            )

    async def chat_message(self, event):
        #print('Sending message to client:', event)
        await self.send(text_data=json.dumps(event))