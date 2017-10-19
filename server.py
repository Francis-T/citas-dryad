from flask import Flask, request, render_template
from threading import Thread
from time import sleep
import socket

HOST = 'localhost'        # Symbolic name meaning all available interfaces
PORT = 50007              # Arbitrary non-privileged port

available_commands = [
    { "cmd_name" : "QSTAT", "desc" : "Retrieves the system status" },
    { "cmd_name" : "QTSET", "desc" : "Sets the time" },
    { "cmd_name" : "QACTV", "desc" : "Activates this Aggregator Node" },
    { "cmd_name" : "QDEAC", "desc" : "Deactivates this Aggregator Node"},
    { "cmd_name" : "QASCP", "desc" : "Adds new collection parameters"},
    { "cmd_name" : "QCUPD", "desc" : "Updates Aggregator Node information"},
    { "cmd_name" : "QNLST", "desc" : "Lists currently registered Sensor Nodes"},
    { "cmd_name" : "QQRSN", "desc" : "Registers a new sensor node" },
    { "cmd_name" : "QSUPD", "desc" : "Updates an existing sensor node"},
    { "cmd_name" : "QDLTE", "desc" : "Deletes an existing sensor node"},
    { "cmd_name" : "QHALT", "desc" : "Halts the Aggregator Node program"},
    { "cmd_name" : "QRELD", "desc" : "Reloads the Aggregator Node program"},
    { "cmd_name" : "QREBT", "desc" : "Reboots the system"},
    { "cmd_name" : "QPWDN", "desc" : "Powers down the system"},
    { "cmd_name" : "QEXTN", "desc" : "Extends the idle duration for the Aggregator Node"},
    { "cmd_name" : "QSETP", "desc" : "Sets a system parameter"},
    { "cmd_name" : "QPARL", "desc" : "Lists currently saved parameters"},
    { "cmd_name" : "QINFO", "desc" : "Retrieves system info"},
    { "cmd_name" : "QDATA", "desc" : "Retrieves data"},
]

app = Flask(__name__)

###    S.0.1. Flask-Specific Functions    ###

@app.route('/')
def welcome():
    return 'Aggregator Node Protoype Web Interface'

@app.route('/command', methods=['POST', 'GET'])
def command():
    if request.method == "POST":
        user_cmd = request.form['cmd'] + "\r\n"

        resp = send_command(user_cmd)
        print(resp)

        return render_template('template_command.html',response=resp)

    return render_template('template_command.html')

@app.route('/help')
def display_help():

    html_str = ""
    html_str += "<p>Command\t\tDescription<br/>"
    html_str += "========================== ==== == =</p>"
    html_str += "<ul>"
    for cmd in available_commands:
        html_str += "<li>" + cmd['cmd_name'] + " - " + cmd['desc'] + "</li>"

    html_str += "</ul>"

    return html_str

@app.route('/status')
def status():
    resp = send_command("QSTAT:;")
    print(resp)

    return str(resp)

@app.route('/halt')
def halt():
    shutdown_server()

    resp = send_command("QHALT:;")
    print(resp)

    return 'Halting program'

@app.route('/reload')
def reload():
    shutdown_server()

    resp = send_command("QRELD:;")
    print(resp)

    return 'Reloading program'

@app.route('/kill_server')
def kill_server():
    shutdown_server()
    return 'Server shutting down'


###    S.1.1. Utility Functions    ###

def send_command(cmd):
    resp = None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.settimeout(3.0)

        s.sendall(cmd.encode('UTF-8'))

        resp = s.recv(1024)
        s.shutdown(socket.SHUT_RDWR)

    return resp

def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return

