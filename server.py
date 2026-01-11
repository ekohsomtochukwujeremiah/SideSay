from firebase_admin import credentials, initialize_app, firestore
import firebase_admin
from datetime import datetime, timezone
import queue
import json
from functools import lru_cache
import time

credentials = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(credentials)
db = firestore.client()

def month_yyyy(firebase_timestamp):    
    if firebase_timestamp:
        return firebase_timestamp.strftime("%d-%B-%Y")
    return ""

def dd_mm_yyyy(firebase_timestamp):
    if firebase_timestamp:
        return firebase_timestamp.strftime("%d-%m-%Y")
    return ""

@lru_cache(maxsize=128)
def get_name_by_username(username):
    user_ref = db.collection("users").document(username)
    user = user_ref.get().to_dict()
    return user['name']

@lru_cache(maxsize=128)
def get_joined_date(username):
    user_ref = db.collection("users").document(username)
    user = user_ref.get().to_dict()
    return user['date_joined']

@lru_cache(maxsize=128)
def get_bio_by_username(username):
    user_ref = db.collection("users").document(username)
    user = user_ref.get().to_dict()
    return user['bio']

def get_username_by_loginkey(login_key):
    try:
        user_ref = db.collection("users").where('login_key', '==', login_key).stream()
        for user in user_ref:
            return user.to_dict()['username']
        return False
    except Exception as error:
        print(f'Error : {error}')

def get_email(username):
    try:
        user_ref = db.collection("users").document(username)
        user = user_ref.get()
        if user.exists:
            return user.to_dict().get('email', '')
        return ""
    except:
        return ""


def is_new_email(email):
    try : 
        user_ref = db.collection("users")
        query = user_ref.where('email', '==', email).stream()  
        if any(query):
            return False 
        else: 
            return True
    except Exception as error:
        print(f'Error : {error}')

def is_new_username(username):
    try : 
        user_ref = db.collection("users")
        query = user_ref.where('username', '==', username).stream()  
        if any(query):
            return False 
        else: 
            return True
    except Exception as error:
        print(f'Error : {error}')



def new(username, name, email, password, login_key, bio):
    try:
        user_ref = db.collection("users").document(username)
        user_ref.set({
            "username" : username,
            "name": name,
            "email": email,
            "password": password,
            "login_key": login_key,
            "bio" : bio,
            "date_joined": firestore.SERVER_TIMESTAMP
        })
        push_system_notification(username, f'Account Created successfully : @{username}')
        print(f"user : {username} created successfully")
    except Exception as error:
        print(f'Error : {error}')

def exists(username):
    try:
        user_ref = db.collection("users").document(username)
        user = user_ref.get()
        if user.exists:
            return True
        else:
            return False
    except Exception as error:
        print(f'Error : {error}')

def correct_credetials(username, password):
    try:
        user_ref = db.collection("users").document(username)
        user = user_ref.get().to_dict()
        if user['password'] == password:
            return True
        else:
            return False
    except Exception as error:
        print(f'Error : {error}')
        return False

def verify_user_login(username, password):
    try:
        user_ref = db.collection("users").document(username)
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data.get('password') == password:
                return user_data
        return False
    except Exception as error:
        print(f'Error : {error}')
        return False


def send_message(sender, receiver, message, time, date):
    sender_ref = db.collection("users").document(sender)
    sender_ref.collection("messages").add({
        'sender' : sender,
        'receiver' : receiver,
        'message' : message,
        'time' : time,
        'date' : date
    })
    receiver_ref = db.collection("users").document(receiver)
    receiver_ref.collection("messages").add({
        'sender' : sender,
        'receiver' : receiver,
        'message' : message,
        'time' : time,
        'date' : date
    })

def add_friend(user, friend):
    user_ref = db.collection("users").document(user)
    user_ref.collection("friends").document(friend).set({
        'username' : friend,
        'connection_date' : firestore.SERVER_TIMESTAMP
    })
    friend_ref = db.collection("users").document(friend)
    friend_ref.collection("friends").document(user).set({
        'username' : user,
        'connection_date' : firestore.SERVER_TIMESTAMP
    })

def remove_friend(user, friend):
    user_ref = db.collection("users").document(user)
    friend_ref = db.collection("users").document(friend)
    user_ref.collection("friends").document(friend).delete()
    friend_ref.collection("friends").document(user).delete()

def friend_list(user):
    user_ref = db.collection("users").document(user)
    friends = user_ref.collection("friends").stream()
    friend_list = []
    for friend in friends:
        user_data = friend.to_dict()
        friend_list.append(user_data['username'])
    return friend_list

#function to accept friend request 
def friend_request_accepted(user, friend):
    user_ref = db.collection("users").document(user)
    docs = user_ref.collection("notifications").where('type', '==', 'friend_request').where('notification', '==', f"User '{friend}' sent you a friend request.").stream()
    for doc in docs:
        doc.reference.delete()
    add_friend(user, friend)
    add_friend(friend, user)
    user_ref.collection("sent_requests").document(friend).delete()
    friend_ref = db.collection("users").document(friend)
    friend_ref.collection("pending_external_requests").document(user).delete()
    print('ACCEPT_REQUEST_STATUS : true')


def friend_request_declined(user, friend):
    user_ref = db.collection("users").document(user)
    docs = user_ref.collection("notifications").where('type', '==', 'friend_request').where('notification', '==', f"User '{friend}' sent you a friend request.").stream()
    for doc in docs:
        doc.reference.delete()
    user_ref.collection("sent_requests").document(friend).delete()
    friend_ref = db.collection("users").document(friend)
    friend_ref.collection("pending_external_requests").document(user).delete()
    print('DECLINE_REQUEST_STATUS : true')

def send_friend_request(user, friend):
    user_ref = db.collection("users").document(user)
    user_ref.collection("notifications").add({
        'type' : 'friend_request',
        'notification' : f"User '{friend}' sent you a friend request.",
        'date' : firestore.SERVER_TIMESTAMP
    })
    user_ref.collection("sent_requests").document(friend).set({
        'username' : friend
    })
    print('SENT_REQUEST_STATUS : true')


def get_relation_status(current_user, target_user):
    if current_user == target_user:
        return 'self'
    
    if db.collection("users").document(current_user).collection("friends").document(target_user).get().exists:
        return 'friend'
    elif db.collection("users").document(current_user).collection("sent_requests").document(target_user).get().exists:
        return 'pending'
    elif db.collection("users").document(current_user).collection("pending_external_requests").document(target_user).get().exists:
        return 'incoming'
    else:
        return 'connect'

def search_friend(friend, current_user=None):
    try:
        user_ref = db.collection("users").document(friend)
        user_doc = user_ref.get()
        
        if user_doc.exists:
            user = user_doc.to_dict()
            date_joined = user.get('date_joined')
            formatted_date = date_joined.strftime("%B-%Y") if date_joined else ""
            
            data = {
                'username' : user.get('username', friend), 
                'name' : user.get('name', friend), 
                'bio': user.get('bio', ''), 
                'date_joined': formatted_date, 
                'verified_badge': user.get('verified_badge', False),
                'development_member': user.get('development_member', False),
                'premium_badge': user.get('premium_badge', False)
            }
            
            if current_user and current_user != friend:
                data['status'] = get_relation_status(current_user, friend)
            
            return data
        return False
    except Exception as error:
        print(f'Error : {error}')
        return False
    
def notifications(user):
    user_ref = db.collection("users").document(user)
    notifications = user_ref.collection("notifications").stream()
    notifications_list = []
    for i in notifications:
        notification_data = i.to_dict()
        notifications_list.append(notification_data)
    return notifications_list


def push_system_notification(user, notification):
    try :
        user_ref = db.collection("users").document(user)
        user_ref.collection("notifications").add({
            'type' : 'system',
            'notification' : notification,
            'date' : firestore.SERVER_TIMESTAMP
        })
        print("succesfully send notification to server")
        return True
    except Exception as error:
        print(f'Error : {error}')
        return False
    
def push_security_notification(user, notification):
    try :
        user_ref = db.collection("users").document(user)
        user_ref.collection("notifications").add({
            'type' : 'security',
            'notification' : notification,
            'date' : firestore.SERVER_TIMESTAMP
        })
        print("succesfully send notification to server")
        return True
    except Exception as error:
        print(f'Error : {error}')
        return False
    
def delete_old_notfications(user):
    try :
        deleted = False
        user_ref = db.collection("users").document(user).collection("notifications").stream()
        for notification in user_ref:
            notification_date = notification.get('date')
            now = datetime.now(timezone.utc)
            diff = now - notification_date
            if diff.days > 7:
                notification.reference.delete()
                deleted = True
        if deleted:
            print("Hit : No old nofications to delete .")
        else:
            print("Hit : Old notifications are deleted successfully .")
    except Exception as error:
        print(f'Error : {error}')
    
    
    
    
def show_friend_profile(friend):
    user_ref = db.collection("users").document(friend)
    user_doc = user_ref.get()
    
    if user_doc.exists:
        user = user_doc.to_dict()
        date_joined = user.get('date_joined')
        formatted_date = date_joined.strftime("%B-%Y") if date_joined else ""
        data = {
            'username' : user.get('username', friend),
            'name' : user.get('name', friend),
            'bio' : user.get('bio', ''),
            'date_joined': formatted_date,
            'verified_badge': user.get('verified_badge', False),
            'development_member': user.get('development_member', False),
            'premium_badge': user.get('premium_badge', False)
        }
        return data
    return {}


#--------------------MESSAGING SYSTEM-------------------------------------# 
def push_to_chat_list(user, friend):
    user_ref = db.collection("users").document(user)
    user_ref.collection("chat_list").document(friend).set({
        'username' : friend
    }, merge=True)

def push_message(sender, receiver, message, time, date):
    try:
        # Use batch write for atomicity and speed
        batch = db.batch()
        
        sender_msg_ref = db.collection("users").document(sender).collection("chat_list").document(receiver).collection("messages").document()
        receiver_msg_ref = db.collection("users").document(receiver).collection("chat_list").document(sender).collection("messages").document()
        
        # References to the chat list documents themselves (for metadata)
        sender_chat_ref = db.collection("users").document(sender).collection("chat_list").document(receiver)
        receiver_chat_ref = db.collection("users").document(receiver).collection("chat_list").document(sender)
        
        timestamp = firestore.SERVER_TIMESTAMP
        
        msg_data = {
            'sender' : sender,
            'receiver' : receiver,
            'message' : message,
            'time' : time,
            'date' : date,
            'timestamp': timestamp
        }
        
        # Metadata to update in the chat list document (denormalization for speed)
        list_update_data = {
            'username': receiver, # Will be overwritten to 'sender' for the other user below
            'last_message': message,
            'time': time,
            'date': date,
            'timestamp': timestamp,
            'sender': sender
        }
        
        batch.set(sender_msg_ref, msg_data)
        batch.set(receiver_msg_ref, msg_data)
        
        # Update chat list docs with last message info
        batch.set(sender_chat_ref, {**list_update_data, 'username': receiver}, merge=True)
        batch.set(receiver_chat_ref, {**list_update_data, 'username': sender}, merge=True)
        
        batch.commit()
        print("Hit : message sent succesfully (batch)!")
    except Exception as error:
        print(f'Error : {error}')


def load_chat_list(user):
    user_ref = db.collection("users").document(user)
    chats = user_ref.collection("chat_list").stream()
    
    chat_list = []
    for chat in chats:
        data = chat.to_dict()
        friend_username = data.get('username')
        
        ts = 0
        if data.get('timestamp'):
            try:
                ts = data.get('timestamp').timestamp()
            except:
                ts = 0
        
        # Optimization: Use denormalized data if available
        if 'last_message' in data:
            chat_list.append({
                'username': friend_username,
                'last_message': data.get('last_message'),
                'time': data.get('time'),
                'date': data.get('date'),
                'sender': data.get('sender'),
                'timestamp': ts
            })
        else:
            # Fallback for legacy data: fetch last message from subcollection
            try:
                last_msg_query = user_ref.collection("chat_list").document(friend_username).collection("messages").order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1).get()
                if last_msg_query:
                    last_msg = last_msg_query[0].to_dict()
                    lm_ts = 0
                    if last_msg.get('timestamp'):
                        try:
                            lm_ts = last_msg.get('timestamp').timestamp()
                        except:
                            lm_ts = 0
                    chat_list.append({
                        'username': friend_username,
                        'last_message': last_msg.get('message'),
                        'time': last_msg.get('time'),
                        'date': last_msg.get('date'),
                        'sender': last_msg.get('sender'),
                        'timestamp': lm_ts
                    })
                else:
                     chat_list.append({'username': friend_username, 'last_message': '', 'time': '', 'date': '', 'sender': '', 'timestamp': 0})
            except:
                chat_list.append({'username': friend_username, 'last_message': '', 'time': '', 'date': '', 'sender': '', 'timestamp': 0})
    
    # Sort by timestamp descending (newest first) in Python to handle legacy data safely
    chat_list.sort(key=lambda x: x.get('timestamp') or 0, reverse=True)
    
    return chat_list

def load_chats(user, friend, after_timestamp=None):
    user_ref = db.collection("users").document(user)
    messages_ref = user_ref.collection("chat_list").document(friend).collection("messages")
    
    if after_timestamp:
        try:
            dt = datetime.fromtimestamp(float(after_timestamp), tz=timezone.utc)
            friend_chat_section = messages_ref.where('timestamp', '>', dt).order_by('timestamp').stream()
        except Exception:
            return []
    else:
        friend_chat_section = messages_ref.order_by('timestamp').limit_to_last(50).get()

    chats = []
    for message in friend_chat_section:
        data = message.to_dict()
        if data['sender'] == user:
            data['sender'] = 'me'
        if data['receiver'] == user:
            data['sender'] = 'user'
        if data['sender'] == friend:
            data['sender'] = 'friend'
        if data['receiver'] == friend:
            data['receiver'] = 'friend'
            
        ts = 0
        if data.get('timestamp'):
            ts = data.get('timestamp').timestamp()
            
        output = {
            'id': message.id,
            'sender' : data['sender'],
            'receiver' : data['receiver'],
            'message' : data['message'],
            'time' : data['time'],
            'date' : data['date'],
            'timestamp': ts
        }
        chats.append(output)
    return chats

def listen_for_messages(user, friend, after_timestamp=None):
    user_ref = db.collection("users").document(user)
    messages_ref = user_ref.collection("chat_list").document(friend).collection("messages")
    
    # Queue to transfer data from Firestore callback to Flask generator
    q = queue.Queue()
    
    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                
                # Normalize sender for frontend
                sender_type = 'me' if data['sender'] == user else 'friend'
                
                ts = 0
                if data.get('timestamp'):
                    ts = data.get('timestamp').timestamp()
                
                output = {
                    'id': change.document.id,
                    'sender': sender_type,
                    'message': data['message'],
                    'time': data['time'],
                    'date': data['date'],
                    'timestamp': ts
                }
                q.put(output)

    # Listen to the last 50 messages and any new ones
    # limit_to_last prevents loading the entire history on every connection
    if after_timestamp and float(after_timestamp) > 0:
        try:
            dt = datetime.fromtimestamp(float(after_timestamp), tz=timezone.utc)
            query = messages_ref.where('timestamp', '>', dt).order_by('timestamp')
        except:
            query = messages_ref.order_by('timestamp').limit_to_last(50)
    else:
        query = messages_ref.order_by('timestamp').limit_to_last(50)
        
    watch = query.on_snapshot(on_snapshot)
    
    # Send retry instruction for client reconnection
    yield "retry: 1000\n\n"
    
    start_time = time.time()
    
    try:
        while True:
            # Rotate connection before Gunicorn timeout (30s default)
            if time.time() - start_time > 25:
                break
                
            try:
                # Wait for new data (timeout allows sending keep-alive)
                msg = q.get(timeout=1)
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                # Send a comment with padding to force flush through Nginx/proxy buffers
                yield ": keep-alive " + (" " * 1024) + "\n\n"
    except GeneratorExit:
        pass
    except Exception as e:
        print(f"Stream Error: {e}")
    finally:
        watch.unsubscribe()

def delete_chats(user, friend):
    try:
        user_ref = db.collection("users").document(user).collection("chat_list").document(friend).delete()
        print("Hit : Chats deleted Successfully....")
    except Exception as error:
        print(f"Error : {error}")

def delete_old_messages(user):
    try:
        user_ref = db.collection("users").document(user).collection("chat_list").stream()
        for chat in user_ref:
            chat_ref = db.collection("users").document(user).collection("chat_list").document(chat.id).collection("messages").stream()
            for message in chat_ref:
                if message.get('timestamp'):
                    dt = datetime.fromtimestamp(float(message.get('timestamp')), tz=timezone.utc)
                    now = datetime.now(timezone.utc)
                    diff = now - dt
                    if diff.days > 7:
                        message.reference.delete()
    except Exception as error:
        print(f"Error : {error}")
