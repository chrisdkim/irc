import os
import uuid, psycopg2, psycopg2.extras
from flask import Flask, session, render_template, redirect, request, url_for
from flask.ext.socketio import SocketIO, emit

app = Flask(__name__, static_url_path='')
#app.config['SECRET_KEY'] = 'secret!'

socketio = SocketIO(app)

messages = []
users = {}

app.secret_key = os.urandom(24).encode('hex')

def connectToIRC():
    connectionString = 'dbname=irc user=postgres password=Password01 host=localhost'
    try:
        return psycopg2.connect(connectionString)
    except:
        print("Unable to connect to database IRC")

def updateRoster():
    names = []
    print "UPDATE ROSTER"
    print "%d browsers are currently connected!" % len(users)
    for user_id in users:
        print "User in Roster: " + users[user_id]['username']
        if len(users[user_id]['username'])==0:
            print "Hmmm, username " + users[user_id]['username'] + " is blank??"
            names.append('Anonymous')
        else:
            names.append(users[user_id]['username'])
            
    username = users[session['uuid']]['username']
    print 'Tell the browser the current username is %s' % username
    emit('identify', username);
    
    print 'Tell the browser the list of connected users'
    emit('roster', names, broadcast=True)
    
@socketio.on('connect', namespace='/chat')
def on_connect():
    print "CONNECT"
    session['uuid']=uuid.uuid1()
    print session['uuid']
    session['username']='starter name'
    print 'connected'
    
    users[session['uuid']]={'username':'Anonymous', 'id':-1}
    updateRoster()
    if session:
        for message in messages:
            emit('message', message)

@socketio.on('message', namespace='/chat')
def new_message(message):
    print "MESSAGE"
    tmp = {'text':message, 'name':users[session['uuid']]['username']}
    messages.append(tmp)
    
    # if the user is signed in, then save to the db
    user = users[session['uuid']];
    userId = user.get('id');
    print "Current userid is %d" % userId;
    if userId >= 0:
        conn = connectToIRC();
        conn.autocommit = True;
        cur = conn.cursor();
    
        print "Attempting to insert message to db";
        insert_msg = "insert into messages (id, username, message) VALUES (default, %s, %s)";
        cur.execute(insert_msg,(str(userId), message));
        conn.commit;
        print "message inserted";
        
    emit('message', tmp, broadcast=True)

@socketio.on('search', namespace='/chat')
def on_search(search):
    print 'SEARCH'
    print "Attempting to search for %s" % search

    conn = connectToIRC();
    conn.autocommit = True;
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "select u.id, u.username, m.message from messages m, users u where u.id::varchar(255) = m.username and m.message like '%" + search + "%'"
    cur.execute(query)
    results = cur.fetchall()
    print "found %d search results" % len(results)
    for message in results:
        print message
        msg = {'text':message['message'], 'name':message['username']}
        emit('message', msg)
    updateRoster()
    
@socketio.on('identify', namespace='/chat')
def on_identify(message):
    print 'IDENTIFY'
    updateRoster()

@socketio.on('login', namespace='/chat')
def on_login(json):
    print 'LOGIN'
    print "Raw Data: %s" % json
    username = json['username']
    password = json['password']
    print "Username from form: %s" % username
    print "Password from form: %s" % password
    print "This request is coming from the Anonymous user with uuid: "
    print "%s" % session['uuid']
    
    print "Let's connect to the database and attempt to authenticate user ..."
    conn = connectToIRC()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    query = "select * from users where username = %s and password = %s"
    cur.execute(query, (username, password))
    
    results = cur.fetchone()
    if results:
        print "Successfully logged in as %s!" % username
        users[session['uuid']]={'username':results[1], 'id':results[0]}
        
        # Load any previous messages
        currUserId = results['id']
        print "Attempting to find messages for userid %s" % currUserId
        query = "select u.id, u.username, m.message from messages m, users u where u.id::varchar(255) = m.username and m.username = %s"
        cur.execute(query, (str(currUserId)));
        userMessages = cur.fetchall();
        print "Found %d messages for user" % len(userMessages)
        for message in userMessages:
            msg = {'text':message['message'], 'name':message['username']}
            emit('message', msg)
    else: 
        users[session['uuid']]={'username':'Anonymous', 'id':-1}
        print "Invalid username or password for %s" % username
        
    updateRoster()
    
@socketio.on('disconnect', namespace='/chat')
def on_disconnect():
    print 'disconnect'
    if session['uuid'] in users:
        del users[session['uuid']]
        updateRoster()

@app.route('/')
def hello_world():
    print 'in hello world'
    return app.send_static_file('index.html')

@app.route('/js/<path:path>')
def static_proxy_js(path):
    # send_static_file will guess the correct MIME type
    return app.send_static_file(os.path.join('js', path))
    
@app.route('/css/<path:path>')
def static_proxy_css(path):
    # send_static_file will guess the correct MIME type
    return app.send_static_file(os.path.join('css', path))
    
@app.route('/img/<path:path>')
def static_proxy_img(path):
    # send_static_file will guess the correct MIME type
    return app.send_static_file(os.path.join('img', path))
    
if __name__ == '__main__':
    print "Starting socketio ... "

    socketio.run(app, host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 8080)))
     