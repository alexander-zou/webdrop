#!/usr/bin/env python
# -*- coding: UTF-8 -*-

'''
@File   : webdrop.py   
@Author : alexander.here@gmail.com
@Date   : 2022-03-14 10:27 CST(+0800)   
@Brief  :  
'''

import os, threading, time, hashlib, netifaces, hashlib, subprocess, sys, platform
import tkinter as tk
import tkinter.messagebox as tkmb
from tkinter import ttk
from tkinter import filedialog as tkfd
from PIL import ImageTk
from flask import Flask, request, make_response, render_template, render_template_string, redirect, abort, send_from_directory
import pyperclip, qrcode

INVALID_FILENAMES = {
    '', 'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

EXPIRATION_SEC = 60 * 60 * 24 * 3
SERVER_WAIT_TIME_MS = 300

TEXTS = {
    'password' : 'password',
    'read_clipboard' : 'Read from Clipboard',
    'write_clipboard' : 'Write to Clipboard',
    'open_url' : 'Open URL',
    'upload' : 'UPLOAD',
    'title' : 'Title',
    'path' : 'Path',
    'browse' : 'Broswe',
    'port' : 'Port',
    'quit' : 'Quit',
    'start' : 'Start',
    'enable_clipboard' : 'Enable Clipboard',
    'error' : 'Error',
    'server_failed' : 'Failed starting server',
    'running' : 'Running',
}
try:
    if os.getenv( 'LANG').startswith( 'zh_') and os.getenv( 'LANG').endswith( '.UTF-8'):
        TEXTS = {
            'password' : '密码',
            'read_clipboard' : '从电脑粘贴板读取',
            'write_clipboard' : '上传至电脑粘贴板',
            'open_url' : '打开URL',
            'upload' : '上传',
            'title' : '标题',
            'path' : '路径',
            'browse' : '浏览',
            'port' : '端口',
            'quit' : '退出',
            'start' : '启动',
            'enable_clipboard' : '开放粘贴板',
            'error' : '错误',
            'server_failed' : '服务器启动失败',
            'running' : '运行中',
        }
except: pass

TEMPLATE_LOGIN = '''
<TITLE>{{ title }} Login</TITLE>
{% block content %}
<div style="padding-top:120px;display:block;text-align:center;">
<form action="/login?url={{ url }}" method="post">
    <label for="pass">{{ texts.password }}:</label>
    <input type="password" name="pass" id="pass" required />
    <input type="submit" value="Login" />
</form>
</div>
{% endblock %}
'''

TEMPLATE_HOMEPAGE = '''
<TITLE>{{ title }}</TITLE>
{% block content %}
    <style>
        .row {
            margin: 6px;
        }
        .uploaded {
            display: grid;
            grid-template-columns: auto 100px 36px 36px;
        }
        .cell {
            display: inline-block;
            background-color: #e6e6e6;
            margin: 1px;
            padding: 5px;
        }
        .center {
            text-align: center;
        }
        .right {
            text-align: right;
        }
        .button {
            height:40px;
            width: 160px;
            line-height: 40px;
            text-align: center;
            margin: 4px;
            display: inline-block;
        }
    </style>
    {% if enable_clipboard %}
    <div style="margin-top:54px">
        <textarea id="text" rows="5" style="width:96%;"></textarea>
        <button class="button" onclick="get_text();">{{ texts.read_clipboard }}↓</button>
        <button class="button" onclick="send_text();">{{ texts.write_clipboard }}↑</button>
        <button class="button" onclick="open_url();">{{ texts.open_url }}</button>
    </div>
    {% endif %}
    <div style="margin-top:54px">
        <div class="row" style="width:320px;">
            <form id="upload_form" action="/upload" method="post" enctype="multipart/form-data">
            <label for="file">[{{ texts.upload }}]</label>
            <input type="file" name="file"/>
            </form>
        </div>
    {% for file in files %}
        <div class="row uploaded">
            <div class="cell"><a href="/download/{{ file[0] }}">{{ file[0] }}</a></div>
            <div class="cell center">{{ file[1] }}</div>
            <div class="cell center" onclick="file_op( 'open', '{{ file[0] }}');">📖</div>
            <div class="cell center" onclick="file_op( 'delete', '{{ file[0] }}');">❌</div>
        </div>
    {% endfor %}
    </div>
    <script type="text/javascript">
        document.getElementById("upload_form").onchange = function() {
            document.getElementById("upload_form").submit();
        };
        function file_op( op, file) {
            var xhttp = new XMLHttpRequest();
            xhttp.open("POST", "/file/" + op + "/" + file, false);
            xhttp.send();
            location.reload(true);
        }
        function get_text() {
            var xhttp = new XMLHttpRequest();
            xhttp.open("POST", '/clipboard?cmd=get&txt=', false);
            xhttp.onreadystatechange=function() {
                if ( xhttp.readyState==4) {
                    document.getElementById('text').value = xhttp.responseText;
                }
            }
            xhttp.send();
        }
        function send_text() {
            var xhttp = new XMLHttpRequest();
            xhttp.open("POST", '/clipboard?cmd=send&txt=' + encodeURIComponent( document.getElementById('text').value), false);
            xhttp.send();
        }
        function open_url() {
            var xhttp = new XMLHttpRequest();
            xhttp.open("POST", '/clipboard?cmd=url&txt=' + encodeURIComponent( document.getElementById('text').value), false);
            xhttp.send();
        }
    </script>
{% endblock %}
'''

# get lan ip:
myips = []
for iface in netifaces.interfaces():
    addrs = netifaces.ifaddresses( iface)
    if netifaces.AF_INET in addrs:
        for elem in addrs[ netifaces.AF_INET]:
            myips.append( elem[ 'addr'])
if len( myips) <= 0:
    myips.append( '127.0.0.1')
myips = list( dict.fromkeys( myips)) # remove duplicates

config_window = tk.Tk()
config_window.title( 'WebDrop')

var_path = tk.StringVar( value=os.getcwd())
var_port = tk.IntVar( value='80')
var_title = tk.StringVar( value=platform.node())
var_ip = tk.StringVar()
var_password = tk.StringVar()
var_clipboard = tk.BooleanVar()
qr_img = None
server_started = False
server_error = None

app = Flask( 'webdrop')

def start_server():
    global server_started, server_error
    try:
        os.chdir( var_path.get())
        server_started = True
        app.run( host='0.0.0.0', port=var_port.get(), debug=False, use_reloader=False)
        server_started = False
    except Exception as e:
        server_started = False
        print( e)
        server_error = str( e)

def readable_size( bytes):
    if bytes < 1024:
        return str( bytes) + 'Bytes'
    kb = bytes / 1024.0
    if kb < 1024:
        return '%.2fKB' % ( kb)
    mb = kb / 1024.0
    if mb < 1024:
        return '%.2fMB' % ( mb)
    gb = mb / 1024.0
    if gb < 1024:
        return '%.2fGB' % ( gb)
    tb = gb / 1024.0
    if tb < 1024:
        return '%.2fTB' % ( tb)
    pb = tb / 1024.0
    return '%.2fPB' % ( pb)

def generate_token( ip, ts):
    md5 = hashlib.md5()
    md5.update( ip.encode('utf-8'))
    md5.update( str( ts).encode('utf-8'))
    md5.update( var_password.get().encode('utf-8'))
    return md5.hexdigest()

def generate_title():
    if len( var_title.get().strip()) > 0:
        return var_title.get() + ' WebDrop'
    else:
        return 'WebDrop'

def system_run( str):
    if sys.platform == 'win32':
        os.startfile( str)
    elif sys.platform == 'darwin':
        subprocess.call( [ 'open', str])
    else:
        subprocess.call( [ 'xdg-open', str])

def is_login():
    if len( var_password.get()) <= 0:
        return True, dict()
    try:
        ip = request.remote_addr
        ts = request.cookies.get( 'ts')
        timepast = int( time.time()) - int( ts)
        if timepast < 0 or timepast > EXPIRATION_SEC:
            return False, dict()
        token = request.cookies.get( 'token')
        if generate_token( ip, ts) == token:
            return True, dict()
    except:
        pass
    if 'ps' in request.values and request.values[ 'ps'] == var_password.get():
        ts = int( time.time())
        token = generate_token( request.remote_addr, ts)
        return True, { 'ts': str( ts), 'token': token}
    return False, dict()

@app.route( '/login', methods=[ 'POST','GET'])
def login():
    if request.method == 'POST' and 'pass' in request.values:
        if request.values[ 'pass'] == var_password.get():
            #success:
            ts = int( time.time())
            token = generate_token( request.remote_addr, ts)
            if 'url' in request.args:
                url = request.args[ 'url']
            else:
                url = '/'
            resp = redirect( url)
            resp.set_cookie( 'ts', str( ts))
            resp.set_cookie( 'token', token)
            return resp
        else:
            time.sleep( 1)
    if 'url' in request.args:
        url = request.args[ 'url']
    else:
        url = '/'
    return render_template_string( TEMPLATE_LOGIN, url=url, title=generate_title(), texts=TEXTS)

@app.route( '/')
def homepage():
    logged, update_cookies = is_login()
    if not logged:
        return redirect( '/login?url=/')
    files = []
    for name in os.listdir( '.'):
        if os.path.isfile( name):
            files.append( ( name, readable_size( os.path.getsize( name))))
    page = make_response( render_template_string( TEMPLATE_HOMEPAGE, files=files, texts=TEXTS,
                                                        enable_clipboard=var_clipboard.get(),
                                                        title=generate_title()
                                                )
                        )
    for k, v in update_cookies.items():
        page.set_cookie( k, v)
    return page

@app.route( '/upload', methods=['POST'])
def upload():
    logged, update_cookies = is_login()
    if not logged:
        abort( 401, 'Must login first')
    if 'file' not in request.files:
        abort( 400, 'Missing file')
    uploaded = request.files[ 'file']
    if uploaded.filename == '':
        abort( 400, 'Missing Filename')
    if uploaded:
        filename = ''.join( filter( lambda x:x not in '<>:"/\|?*', uploaded.filename))
        if filename.upper() in INVALID_FILENAMES:
            abort( 400, 'Invalid filename')
        if os.path.exists( filename):
            abort( 400, 'Already Exists')
        uploaded.save( filename)
        return redirect( '/')
    abort( 400, 'Missing data')    

@app.route( '/download/<string:name>')
def download( name):
    logged, update_cookies = is_login()
    if not logged:
        abort( 401, 'Must login first')
    return send_from_directory( '.', name)

@app.route( '/file/<string:op>/<string:file>', methods=[ 'POST','GET'])
def file_op( op, file):
    logged, update_cookies = is_login()
    if not logged:
        abort( 401, 'Must login first')
    if not os.path.exists( file):
        abort( 404)
    if 'open' == op:
        system_run( file)
    elif 'delete' == op:
        os.remove( file)
    return 'OK'

@app.route( '/clipboard', methods=[ 'POST','GET'])
def clipboard():
    if not var_clipboard.get():
        abort( 401, 'Clipboard Disabled')
    if request.method == 'POST':
        cmd = request.values[ 'cmd']
        txt = request.values[ 'txt']
        if 'get' == cmd:
            return pyperclip.paste()
        elif 'send' == cmd:
            pyperclip.copy( txt)
        elif 'url' == cmd:
            if not txt.lower().startswith( 'http://') and not txt.lower().startswith( 'https://'):
                txt = 'http://' + txt
            system_run( txt)
        return 'OK'
    else:
        logged, update_cookies = is_login()
        if not logged:
            return redirect( '/login?url=/text')
        return render_template( 'text.html')

def click_browse( evt=None):
    new_path = tkfd.askdirectory( initialdir=var_path.get(), mustexist=True, title='选择工作目录')
    if new_path and len( new_path) > 0 and os.path.isdir( new_path):
        var_path.set( new_path)

def click_start( evt=None):
    # disable setting ui:
    global checkbutton_clipboard, button_start, button_browse, entry_pass, entry_port, entry_title
    checkbutton_clipboard.config( state=tk.DISABLED)
    button_start.config( state=tk.DISABLED)
    button_browse.config( state=tk.DISABLED)
    entry_pass.config( state='readonly')
    entry_port.config( state='readonly')
    entry_title.config( state='readonly')

    # try starting server:
    global server_error
    server_error = None
    thread = threading.Thread( target=start_server)
    thread.daemon = True
    thread.start()
    config_window.after( SERVER_WAIT_TIME_MS, check_server)

def draw_qr( evt=None):
    global server_started
    if server_started:
        global qr_img, canvas_qr, config_window
        url = 'http://' + var_ip.get() + ':' + str( var_port.get())
        qr_img = qrcode.make( url).resize( ( 200, 200))
        qr_img = ImageTk.PhotoImage( image=qr_img)
        canvas_qr.delete( tk.ALL)
        canvas_qr.create_image( 0, 0, image=qr_img, anchor=tk.NW)
        config_window.update_idletasks()
        config_window.update()

def check_server():
    global server_error, server_started
    if server_error is None:
        # tkmb.showinfo( title='成功', message='服务器启动成功,URL:\n' + url)
        draw_qr()
    else:
        server_started = False
        tkmb.showerror( title=TEXTS[ 'error'], message=TEXTS[ 'server_failed']+':'+str( server_error))
        global config_window, checkbutton_clipboard, button_start, button_browse, entry_pass, entry_port, entry_title
        config_window.title( 'WebDrop - ' + TEXTS[ 'running'])
        checkbutton_clipboard.config( state=tk.NORMAL)
        button_start.config( state=tk.NORMAL)
        button_browse.config( state=tk.NORMAL)
        entry_pass.config( state=tk.NORMAL)
        entry_port.config( state=tk.NORMAL)
        entry_title.config( state=tk.NORMAL)
        return

frame_lines = [ tk.Frame( config_window), tk.Frame( config_window), tk.Frame( config_window)]

for frame in frame_lines:
    frame.pack( side=tk.TOP, fill=tk.X, pady=4)

tk.Label( frame_lines[ 0], anchor=tk.E, text=TEXTS[ 'title']).pack( side=tk.LEFT, padx=4)
entry_title = tk.Entry( frame_lines[ 0], textvariable=var_title, width=10)
entry_title.pack( side=tk.LEFT)
tk.Label( frame_lines[ 0], anchor=tk.E, text=TEXTS[ 'path']).pack( side=tk.LEFT, padx=4)
entry_path = tk.Entry( frame_lines[ 0], textvariable=var_path, state='readonly')
entry_path.pack( side=tk.LEFT, fill=tk.X, expand=tk.YES)
button_browse = tk.Button( frame_lines[ 0], text=TEXTS[ 'browse']+'...', command=click_browse)
button_browse.pack( side=tk.RIGHT, padx=2)

tk.Label( frame_lines[ 1], anchor=tk.E, text='IP').pack( side=tk.LEFT, padx=4)
combobox_ip = ttk.Combobox( frame_lines[ 1], textvariable=var_ip, state='readonly', values=myips)
combobox_ip.current( len( myips)-1)
combobox_ip.pack( side=tk.LEFT)
combobox_ip.bind( "<<ComboboxSelected>>", draw_qr)
tk.Label( frame_lines[ 1], anchor=tk.E, text=TEXTS[ 'port']).pack( side=tk.LEFT, padx=4)
entry_port = tk.Entry( frame_lines[ 1], textvariable=var_port, width=6)
entry_port.pack( side=tk.LEFT)
tk.Label( frame_lines[ 1], anchor=tk.E, text=TEXTS[ 'password']).pack( side=tk.LEFT, padx=4)
entry_pass = tk.Entry( frame_lines[ 1], textvariable=var_password)
entry_pass.pack( side=tk.LEFT, fill=tk.X, expand=tk.YES)

canvas_qr = tk.Canvas( frame_lines[ 2], width=200, height=200)
canvas_qr.pack( side=tk.LEFT)
button_close = tk.Button( frame_lines[ 2], text=TEXTS[ 'quit'], command=exit)
button_close.pack( side=tk.RIGHT, padx=4, anchor=tk.S)
button_start = tk.Button( frame_lines[ 2], text=TEXTS[ 'start'], command=click_start)
button_start.pack( side=tk.RIGHT, padx=4, anchor=tk.S)
checkbutton_clipboard = tk.Checkbutton( frame_lines[ 2], anchor=tk.W, text=TEXTS[ 'enable_clipboard'], variable=var_clipboard)
checkbutton_clipboard.pack( side=tk.RIGHT, padx=4, anchor=tk.S)

config_window.mainloop()

# End of 'webdrop.py' 

