from flask import Flask, render_template, redirect, request, session, jsonify, Response
from server import *
from security import *
import os

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "app_secret_key")


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            user_data = verify_user_login(username, password)
            if user_data:
                session['username'] = username
                session['name'] = user_data.get('name')
                push_new_session_notification(username, request.user_agent.string)
                return redirect('/chat')
            return render_template('home.html', error="Wrong Credentials")
        except Exception as error:
            print(f'Error : {error}')
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "POST":
        username = request.form.get('username')
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        login_key = request.form.get('login_key')
        bio = request.form.get('bio')
        print(f'Hit : [({username}) ({name}) ({email}) ({password}) ({login_key}) ({bio})] added successfully....')
        new(username, name, email, password, login_key, bio)
        session['username'] = username
        session['name'] = name
        return redirect('/chat')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        passwd = request.form.get('password')
        print(user, passwd)
        user_data = verify_user_login(user, passwd)
        if user_data:
            session['username'] = user
            session['name'] = user_data.get('name')
            return redirect("/chat")
        return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/login-key', methods=['GET', 'POST'])
def login_key():
    if request.method == "POST":
        key = request.form.get("security_key")
        user = get_username_by_loginkey(key)
        if user:
            session['username'] = user
            session['name'] = get_name_by_username(user)
            return redirect("/chat")
        return render_template('login_via_key.html', error="Invalid Security Key")
    return render_template('login_via_key.html')


@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect('/')
    delete_old_notfications(session['username'])
    
    user_data = search_friend(session['username'])
    # Fallback values if user_data is missing (though it should exist for logged in user)
    name = user_data.get('name', 'User') if user_data else 'User'
    bio = user_data.get('bio', '') if user_data else ''
    joined_date = user_data.get('date_joined', '') if user_data else ''
    development_member = user_data.get('development_member', False) if user_data else False
    premium_badge = user_data.get('premium_badge', False) if user_data else False
    email = get_email(session['username'])
    
    return render_template('privalk.html', username=session['username'], name=name, bio=bio, joined_date=joined_date, development_member=development_member, premium_badge=premium_badge, email=email)

@app.route('/chat/add_friend', methods=['POST'])
def send_req():
    friend = request.form.get("friend_username")
    result = search_friend(friend, session['username'])
    return jsonify(result)

@app.route('/chat/load_notifications')
def load_notifications():
    notif_list = notifications(session['username'])
    for n in notif_list:
        if 'date' in n:
            try:
                n['date'] = n['date'].strftime("%d-%B-%Y %H:%M")
            except:
                n['date'] = str(n['date'])
    return jsonify(notif_list)

@app.route('/chat/check_status/<friend>')
def check_status(friend):
    return jsonify({'status': get_relation_status(session['username'], friend)})

@app.route('/chat/search/connect', methods=['POST'])
def connect():
    send_friend_request(request.form.get('friend_username'), session['username'])
    return jsonify({'status': 'success'})

@app.route('/chat/remove_friend', methods=['POST'])
def remove_friend_route():
    data = request.get_json()
    remove_friend(session['username'], data.get('username'))
    return jsonify({'status': 'success'})


@app.route('/chat/load_chat_list')
def load_chat_list_section():
    username = session['username']
    # load_chat_list now returns the full data structure with messages
    friends_data = load_chat_list(username)
    
    data = []
    for chat in friends_data:
        # Optimization: Only fetch name if not already denormalized in server.py
        if not chat.get('name'):
            friend_username = chat['username']
            name = get_name_by_username(friend_username)
            chat['name'] = name if name else friend_username
        data.append(chat)
        
    return jsonify(data)

@app.route('/chat/load_chats/<friend>')
def load_chats_section(friend):
    after = request.args.get('after')
    return jsonify(load_chats(session['username'], friend, after))

@app.route('/chat/stream/<friend>')
def stream_chat(friend):
    after = request.args.get('after')
    response = Response(listen_for_messages(session['username'], friend, after), mimetype='text/event-stream')
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/chat/load_chat/<friend>/send_message', methods=['GET', 'POST'])
def send_message(friend):
    user = request.values.get('user')
    message = request.values.get('message')
    time = request.values.get('time')
    date = request.values.get('date')
    sender_name = request.values.get('sender_name')
    receiver_name = request.values.get('receiver_name')
    # push_to_chat_list calls removed as push_message handles it in batch
    push_message(user, friend, message, time, date, sender_name, receiver_name)
    return jsonify({'status': 'success'})

@app.route('/chat/delete_chats/<friend>')
def delete_chats_section(friend):
    delete_chats(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/chat/report/<friend>')
def report_friend(friend):
    # Log report or handle logic
    print(f"REPORT: User {session.get('username')} reported {friend}")
    return jsonify({'status': 'success'})

@app.route('/check_email', methods=['POST'])
def check_email():
    data = request.get_json()
    return jsonify({'is_new': is_new_email(data.get('email'))})

@app.route('/check_username', methods=['POST'])
def check_username():
    data = request.get_json()
    return jsonify({'is_new': is_new_username(data.get('username'))})

@app.route('/friend')
def load_friends():
    return jsonify(friend_list(session['username']))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/friend/delete/<friend>')
def delete_friend(friend):
    remove_friend(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/friend_request_accepted/<friend>')
def request_accepted(friend):
    friend_request_accepted(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/friend_request_declined/<friend>')
def request_declined(friend):
    friend_request_declined(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/show_profile/<friend>')
def show_profile(friend):
    return jsonify(show_friend_profile(friend))


@app.route('/security/enable_2fa')
def enable_2fa():
    two_factor_authentication(session['username'], True)
    push_security_notification(session['username'], '2FA Enabled')
    return jsonify({'status': 'success'})

@app.route('/security/disable_2fa')
def disable_2fa():
    two_factor_authentication(session['username'], False)
    push_security_notification(session['username'], '2FA Disabled')
    return jsonify({'status': 'success'})

@app.route('/security/block/<friend>')
def block_friend(friend):
    block(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/security/unblock/<friend>')
def unblock_friend(friend):
    unblock(session['username'], friend)
    return jsonify({'status': 'success'})

@app.route('/security/fetch_block_list')
def fetch_block_list_section():
    return jsonify(fetch_block_list(session['username']))

@app.route('/security/fetch_sessions')
def fetch_sessions_section():
    return jsonify(fetch_sessions(session['username']))

@app.route('/security/change_password', methods=['POST'])
def update_password_route():
    data = request.get_json()
    if change_password(session['username'], data.get('old_password'), data.get('new_password')):
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Incorrect old password'})

@app.route('/security/delete_account', methods=['POST'])
def delete_account_route():
    data = request.get_json()
    password = data.get('password')
    
    if correct_credetials(session['username'], password):
        account_delete(session['username'])
        session.clear()
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Incorrect password'})

@app.route('/security/2fa/set', methods=['POST'])
def set_2fa_route():
    two_factor_authentication(session['username'], request.get_json().get('status'))
    push_security_notification(session['username'], '2FA Status Updated')
    return jsonify({'status': 'success'})

@app.route('/security/2fa/status')
def get_2fa_status_route():
    return jsonify({'status': get_2fa_status(session['username'])})

@app.route('/security/verified_badge/set', methods=['POST'])
def set_verified_badge_route():
    verified_badge_status(session['username'], request.get_json().get('status'))
    push_security_notification(session['username'], 'Verified Badge Updated')
    return jsonify({'status': 'success'})

@app.route('/security/verified_badge/status')
def get_verified_badge_status_route():
    return jsonify({'status': get_verified_badge_status(session['username'])})

@app.route('/security/change_password')
def change_password_section():
    old_password = request.args.get('old_password')
    new_password = request.args.get('new_password')
    if change_password(session['username'], old_password, new_password):
        push_security_notification(session['username'], 'Password Updated')
        return jsonify({'status': 'success'})
    return jsonify({'status': 'failure'})

@app.route('/security/delete_account')
def delete_account():
    account_delete(session['username'])
    session.clear()
    return redirect('/')

@app.route('/update/username')
def update_username_route():
    new_username = request.args.get('username')
    result = update_username(session['username'], new_username)
    if 'Error' in result:
        return jsonify({'status': 'error', 'message': result['Error']})
    session['username'] = new_username
    return jsonify({'status': 'success'})

@app.route('/update/email')
def update_email_route():
    new_email = request.args.get('email')
    result = update_email(session['username'], new_email)
    if 'Error' in result:
        return jsonify({'status': 'error', 'message': result['Error']})
    push_security_notification(session['username'], 'Email Updated')
    session['email'] = new_email
    return jsonify({'status': 'success'})

@app.route('/update/name')
def update_name_route():
    new_name = request.args.get('name')
    result = update_name(session['username'], new_name)
    if 'Error' in result:
        return jsonify({'status': 'error', 'message': result['Error']})
    push_system_notification(session['username'], 'Name Updated')
    session['name'] = new_name
    return jsonify({'status': 'success'})

@app.route('/update/bio')
def update_bio_route():
    new_bio = request.args.get('bio')
    result = update_bio(session['username'], new_bio)
    if 'Error' in result:
        return jsonify({'status': 'error', 'message': result['Error']})
    session['bio'] = new_bio
    push_system_notification(session['username'], 'Bio Updated')
    return jsonify({'status': 'success'})

@app.route('/update/login_key')
def update_login_key_route():
    new_login_key = request.args.get('new_login_key')
    password = request.args.get('password')
    if correct_credetials(session['username'], password):
        result = update_login_key(session['username'], new_login_key)
        if 'Error' in result:
            return jsonify({'status': 'error', 'message': result['Error']})
        push_security_notification(session['username'], 'Login Key Updated')
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Incorrect password'})




if __name__ == '__main__':
    app.run(debug=True)