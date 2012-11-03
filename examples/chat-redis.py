import time, cgi, os

from diesel import Service, Application, sleep, first, Loop

from diesel.web import DieselFlask
from diesel.protocols.websockets import WebSocketDisconnect

from diesel.util.queue import Fanout
from diesel.protocols.redis import RedisSubHub, RedisClient
from simplejson import dumps, loads, JSONDecodeError

content = '''
<html>
<head>
<script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js" type="text/javascript"></script>
<script>

var chatter = new WebSocket("ws://" + document.location.host + "/ws");

chatter.onopen = function (evt) {
}

chatter.onmessage = function (evt) {
    var res = JSON.parse(evt.data);
    var p = $('#the-chat');
    var add = $('<div class="chat-message"><span class="nick">('+ res.chan +') &lt;' + res.nick +
    '&gt;</span> ' + res.message + '</div>');
    p.append(add);
    if (p.children().length > 15)
        p.children().first().remove();
}

function push () {
    chatter.send(JSON.stringify({
        channel: $('#the-channel').val(),
        message: $('#the-message').val(),
        nick: $('#the-nick').val()
    }));
    $('#the-message').val('');
    $('#the-message').focus();
}

$(function() {
    $('#the-button').click(push);
    $('#the-message').keyup(function (evt) { if (evt.keyCode == 13) push(); });
});

</script>

<style>

body {
    width: 800px;
    margin: 25px auto;
}

#the-chat {
    margin: 15px 8px;
}

.chat-message {
    margin: 4px 0;
}


.nick {
    font-weight: bold;
    color: #555;
}

</style>

</head>
<body>

<h2>Diesel WebSocket Chat</h2>

<div style="font-size: 13px; font-weight: bold; margin-bottom: 10px">
Channel: <input type="text" size="10" id="the-channel" />&nbsp;&nbsp;
Nick: <input type="text" size="10" id="the-nick" />&nbsp;&nbsp;
Message: <input type="text" size="60" id="the-message" />&nbsp;&nbsp;
<input type="button" value="Send" id="the-button"/>
</div>

<div id="the-chat">
</div>

</body>
</html>
'''

app = DieselFlask(__name__)

#hub = RedisSubHub(host="carp.redistogo.com", port=9245, password="79fe5cf7d152e96255f0b730337efb67")
#hub = RedisSubHub(host="grouper.redistogo.com", port=9125, password="f25f47d53aac69e13b5d344c9477e246")
hub =  RedisSubHub("localhost")

@app.route("/")
def web_handler():
    return content

@app.route("/ws")
@app.websocket
def pubsub_socket(req, inq, outq):
    c = hub.make_client()
    print "forking websocket"
    with hub.subq("*") as group:
        while True:
            q, v = first(waits=[inq, group])
            if isinstance(v, WebSocketDisconnect):
                return
            elif q == inq: # getting message from client
                print "(inq) %s" % v
                print req
                cmd = v.get("cmd", "")
                chan = v.get("channel", "default")
                if cmd=="":
                    print "published message to %i subscribers" % c.publish(chan, dumps({
                    'nick' : cgi.escape(v['nick'].strip()),
                    'message' : cgi.escape(v['message'].strip()),
                    }))
                else:
                    outq.put(dict(message="test bot"))
            elif q == group: # getting message for broadcasting
                chan, msg_str = v
                try:
                    msg = loads(msg_str)
                    data = dict(chan=chan, message=msg['message'], nick=msg['nick'])
                    print "(outq) %s" % data
                    outq.put(data)
                except JSONDecodeError:
                    print "error decoding message %s" % msg_str

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.diesel_app.add_loop(Loop(hub))
    app.run(iface='0.0.0.0', port=port)