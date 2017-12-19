import socket
import struct
import sys
import time
import boto3
import datetime




WIWO_mac = '11:22:33:aa:bb:cc'  # the MAC address of the S20 device. consult the README.md for instructions how to get this

# External port that will be forwarded to port 10000 on the S20 device. If you need help with configuring your router look here http://www.wikihow.com/Set-Up-Port-Forwarding-on-a-Router
WIWO_port = 10000
WIWO_ip = 'EXTERNAL IP as seen in https://whatismyipaddress.com, or hostname that resolves to it'

DEFAULT_TIMEOUT = 30    # the default time in seconds after which the S20 will close automatically. enter 0 or negative value to disable automatic close

# Populate with the ID of your lambda function's configured cloudwatch event for the wiwo_timer.
# This ID is can be found in the lambda function's configuration tab, when you press the "CloudWatch Events" box, under the name of the event.
WIWO_CLOUDWATCH_TIMEOUT_EVENT_ARN = "arn:aws:events:<zone>:#:rule/wiwo_timer"

# Adding security if you want.
# Populate with your skill's application ID to prevent someone else from configuring a skill that sends requests to this function.
# This ID is can be found under the Alexa tab on the amazon developer console page
# Goto https://developer.amazon.com/edw/home.html#/skills > Click 'View Skill ID'
CHECK_APP_ID = False
ALEXA_SKILL_APP_ID = "amzn1.ask.skill.#"




class OrviboS20:
    """
    main class for Orvibo S20
    """
    port = 10000

    class UnknownPacket(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __init__(self):
        self.subscribed = None
        self.exitontimeout = False
        # TODO: get a lock (file lock?) for port 10000
        # get a connection sorted
        self.sock = socket.socket(
            socket.AF_INET,  # Internet
            socket.SOCK_DGRAM  # UDP
        )
        # https://stackoverflow.com/questions/11457676/python-socket-error-errno-13-permission-denied
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('', self.port))

    def close(self):
        try:
            self.sock.close()
        except Exception as e:
            print e

    def _settimeout(self, timeout=None):
        self.sock.settimeout(timeout)  # seconds - in reality << 1 is needed, None = blocking (wait forever)

    # takes payload excluding first 4 (magic, size) bytes
    def _sendpacket(self, payload, ip):
        data = [0x68, 0x64, 0x00, len(payload) + 4]
        data.extend(payload)
        # print data
        self.sock.sendto(''.join([struct.pack('B', x) for x in data]), (ip, 10000))

    def _listendiscover(self):
        status = {
            'exit': True,
            'timeout': False,
            'detail': {},
        }
        if self.exitontimeout:
            status['exit'] = False  # we should wait for timeout, not just exit
        # we need to run and catch timeouts
        try:
            data, addr = self.sock.recvfrom(1024)
            # check magic for a valid packet
            if data[0:2] != 'hd':
                return None
            # decode
            status['address'], status['port'] = addr
            status['detail']['length'] = struct.unpack('>H', data[2:4])[0]
            status['detail']['commandid'] = struct.unpack('>H', data[4:6])[0]
            # print "Length: %d" % status['detail']['length']
            # print "commandid: 0x%04x" % status['detail']['commandid']
            # then based on the lenth / command we can expect different stuff
            if status['detail']['length'] == 6 and status['detail']['commandid'] == 0x7161:
                # already got everything
                # global discovery - we probably sent this
                # print "command: Global Discovery"
                status['command'] = 'Global Discovery'
                status['exit'] = False  # expect more after this
            elif status['detail']['length'] == 18 and status['detail']['commandid'] == 0x7167:
                # discovery - we probably sent this
                # print "command: Discovery"
                status['command'] = 'Discovery'
                status['exit'] = False  # expect more after this
                # get remaining stuff
                status['detail']['dstmac'] = struct.unpack('6B', data[6:12])
                status['detail']['srcmac'] = struct.unpack('6B', data[12:18])
            # print "mac: %s" % ':'.join( [ '%02x' % c for c in status['detail']['dstmac']  ] )
            # print "padding: %s" % ':'.join( [ '%02x' % c for c in status['detail']['srcmac'] ] )
            elif status['detail']['length'] == 42 and (
                            status['detail']['commandid'] == 0x7161 or status['detail']['commandid'] == 0x7167):
                # returned discovery
                # print "command: Discovery (response)"
                status['command'] = 'Discovery (response)'
                # get remaining stuff
                zero = struct.unpack('>B', data[6:7])[0]
                if zero != 0:
                    print >> sys.stderr, "WARNING: [0] zero = 0x%02x\n" % zero
                status['detail']['dstmac'] = struct.unpack('6B', data[7:13])
                status['detail']['srcmac'] = struct.unpack('6B', data[13:19])
                dstmacr = struct.unpack('6B', data[19:25])
                srcmacr = struct.unpack('6B', data[25:31])
                # print "mac: %s" % ':'.join( [ '%02x' % c for c in status['detail']['dstmac']  ] )
                # print "padding: %s" % ':'.join( [ '%02x' % c for c in status['detail']['srcmac'] ] )
                status['detail']['soc'] = data[31:37]
                # print "soc: %s" % status['detail']['soc']
                status['detail']['timer'] = struct.unpack('I', data[37:41])[0]
                # print "1900+sec: %d" % status['detail']['timer']
                status['state'] = struct.unpack('B', data[41])[0]
            # print "state: %d" % status['state']
            elif status['detail']['length'] == 24 and status['detail']['commandid'] == 0x636c:
                # returned subscription TODO separate this - we should only be looking for subscription related stuff after and not tricked by other (discovery) stuff
                status['detail']['dstmac'] = struct.unpack('6B', data[6:12])
                status['detail']['srcmac'] = struct.unpack('6B', data[12:18])
                # print "mac: %s" % ':'.join( [ '%02x' % c for c in status['detail']['dstmac']  ] )
                # print "padding: %s" % ':'.join( [ '%02x' % c for c in status['detail']['srcmac'] ] )
                zero = struct.unpack('>5B', data[18:23])
                for i in range(5):
                    if zero[i] != 0:
                        print >> sys.stderr, "WARNING: [1] zero[%d] = 0x%02x\n" % (i, zero)
                status['state'] = struct.unpack('B', data[23])[0]
            # print "state: %d" % status['state']
            elif status['detail']['length'] == 23 and status['detail']['commandid'] == 0x6463:
                # returned power on/off TODO separate this - we should only be looking for subscription related stuff after and not tricked by other (discovery) stuff
                status['detail']['dstmac'] = struct.unpack('6B', data[6:12])
                status['detail']['srcmac'] = struct.unpack('6B', data[12:18])
                # print "mac: %s" % ':'.join( [ '%02x' % c for c in status['detail']['dstmac']  ] )
                # print "padding: %s" % ':'.join( [ '%02x' % c for c in status['detail']['srcmac'] ] )
                status['detail']['peercount'] = struct.unpack('B', data[18])  # number of peers on the network
                zero = struct.unpack('>4B', data[19:23])
                for i in range(4):
                    if zero[i] != 0:
                        print >> sys.stderr, "WARNING: [2] zero[%d] = 0x%02x\n" % (i, zero[i])
                        # previous info said 4 bytes zero, 5th state, but on my S20 this is always zero, so assume as above 5 bytes zero, no state
            else:
                raise OrviboS20.UnknownPacket
        except socket.timeout:
            # if we are doing timeouts then just catch it - it's probably for a reason
            status['timeout'] = True
            if self.exitontimeout:
                status['exit'] = True
        except OrviboS20.UnknownPacket, e:  # TODO this should be more specific to avoid trapping syntax errors
            print >> sys.stderr, "Error: %s:" % e
            print >> sys.stderr, "Unknown packet:"
            for c in struct.unpack('%dB' % len(data), data):
                print >> sys.stderr, "* %02x \"%s\"\n" % (c, chr(c))

        # fill in text MAC
        if 'detail' in status:
            if 'dstmac' in status['detail']:
                status['dstmachex'] = ':'.join(['%02x' % c for c in status['detail']['dstmac']])
            if 'srcmac' in status['detail']:
                status['srcmachex'] = ':'.join(['%02x' % c for c in status['detail']['srcmac']])

        return status

    def subscribe(self, ip, mac):
        self._settimeout(1)
        self.exitontimeout = True
        data = [0x63, 0x6c]
        data.extend([int(x, 16) for x in mac.split(':')])
        data.extend([0x20, 0x20, 0x20, 0x20, 0x20, 0x20])
        data.extend([int(x, 16) for x in reversed(mac.split(':'))])
        data.extend([0x20, 0x20, 0x20, 0x20, 0x20, 0x20])
        self._sendpacket(data, ip)
        resp = self._listendiscover()
        if 'address' not in resp:
            return None

        self.subscribed = [
            resp['address'],
            ''.join([struct.pack('B', x) for x in resp['detail']['dstmac']]),
            # ':'.join ( [ "%02x" % x for x in resp['detail']['dstmac'] ] )
            [x for x in resp['detail']['dstmac']]
        ]
        time.sleep(0.01)  # need a delay >6ms to be reliable - comands before that may be ignored
        return resp

    def _subscribeifneeded(self, ip, mac):
        if mac is None and self.subscribed is not None:
            # already subscribed
            pass
        elif ip is not None and mac is not None:
            # subscribe or check existing subscription
            macasbin = ''.join([struct.pack('B', int(x, 16)) for x in mac.split(':')])
            if self.subscribed is None or self.subscribed[1] != macasbin:
                # new subscription / re-subscription
                resp = self.subscribe(ip, mac)
                print "subscribe response : %s" % str(resp)
                if self.subscribed is None or self.subscribed[1] != macasbin:
                    print('self.subscribe failed: %s' % self.subscribed)  # something failed

    def poweron(self, ip=None, mac=None):
        self._subscribeifneeded(ip, mac)
        # we should now be subscribed - go ahead with the power command
        data = [0x64, 0x63]
        data.extend([int(x, 16) for x in WIWO_mac.split(':')])
        data.extend([0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0x00, 0x01])
        self._sendpacket(data, WIWO_ip)
        resp = self._listendiscover()
        print "poweron response : %s" % str(resp)
        return resp

    def poweroff(self, ip=None, mac=None):
        self._subscribeifneeded(ip, mac)
        # we should now be subscribed - go ahead with the power command
        data = [0x64, 0x63]
        data.extend([int(x, 16) for x in WIWO_mac.split(':')])
        data.extend([0x20, 0x20, 0x20, 0x20, 0x20, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00])
        self._sendpacket(data, WIWO_ip)
        resp = self._listendiscover()
        print "poweroff response : %s" % str(resp)
        return resp


def start_off_timer(timeout_minutes, enable):
    # Create CloudWatchEvents client
    cloudwatch_events = boto3.client('events')

    timeout = datetime.datetime.now() + datetime.timedelta(minutes=timeout_minutes)
    cron_str = "cron(%d %d %d %d ? %d)" % (timeout.minute, timeout.hour, timeout.day, timeout.month, timeout.year)

    # Put an event rule
    response = cloudwatch_events.put_rule(
        Name='wiwo_timer',
        ScheduleExpression=cron_str,
        State=('ENABLED' if enable else 'DISABLED')
    )
    print "start_off_timer response: " + (response['RuleArn'])
    return response['RuleArn'] == WIWO_CLOUDWATCH_TIMEOUT_EVENT_ARN


def stop_off_timer():
    start_off_timer(0, False)


def lambda_handler(event, context):
    print event

    if "account" in event:
        if WIWO_CLOUDWATCH_TIMEOUT_EVENT_ARN in event["resources"]:
            handle_timeout()
        return

    if CHECK_APP_ID and (event["session"]["application"]["applicationId"] != ALEXA_SKILL_APP_ID):
        raise ValueError("Invalid Application ID")

    if event["session"]["new"]:
        on_session_started({"requestId": event["request"]["requestId"]}, event["session"])

    if event["request"]["type"] == "LaunchRequest":
        return on_launch(event["request"], event["session"])
    elif event["request"]["type"] == "IntentRequest":
        return on_intent(event["request"], event["session"])
    elif event["request"]["type"] == "SessionEndedRequest":
        return on_session_ended(event["request"], event["session"])


def on_session_started(session_started_request, session):
    print "Starting new session."


def on_launch(launch_request, session):
    return get_welcome_response()


def on_intent(intent_request, session):
    intent = intent_request["intent"]
    intent_name = intent_request["intent"]["name"]

    if intent_name == "ActionStart":
        return switch_s20_state(True, DEFAULT_TIMEOUT)
    elif intent_name == "ActionStartWithDuration":
        timeout = get_duration_from_intent(intent)
        if timeout <= 0:
            return handle_timeout_value_error()
        return switch_s20_state(True, timeout)
    elif intent_name == "ActionStop":
        return switch_s20_state(False, 0)
    elif intent_name == "AMAZON.CancelIntent":
        return handle_session_end_request()
    else:
        raise ValueError("Invalid intent")


def on_session_ended(session_ended_request, session):
    print "Ending session."
    # Cleanup goes here...


def handle_session_end_request():
    card_title = "Wiwo - Thanks"
    speech_output = ""
    should_end_session = True

    return build_response({}, build_speechlet_response(card_title, speech_output, None, should_end_session))


def get_welcome_response():
    session_attributes = {}
    card_title = "Wiwo controller"
    speech_output = "Welcome to Wiwo controller. Please specify on or off."
    reprompt_text = "Please specify on or off"
    should_end_session = False
    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def get_duration_from_intent(intent):
    print 'get_duration_from_intent: ' + str(intent)

    if "slots" in intent and "Timeout" in intent["slots"]:
        return int(intent["slots"]["Timeout"]["value"])
    else:
        return DEFAULT_TIMEOUT


def handle_timeout_value_error():
    card_title = "Wiwo - timeout error"
    speech_output = "Wiwo timeout value should be a positive number of minutes"
    should_end_session = False

    return build_response({}, build_speechlet_response(card_title, speech_output, None, should_end_session))


def switch_s20_state(enable, timeout):
    print "switch_s20_state: enable=%d, timeout=%d)" % (enable, timeout)

    session_attributes = {}
    card_title = "Wiwo controller state"
    reprompt_text = "Please specify on or off"
    should_end_session = True

    if enable:
        speech_output = "Turning wiwo on for %d minutes" % (timeout)
        with OrviboS20() as control:
            resp = control.poweron(WIWO_ip, WIWO_mac)
        if timeout > 0:
            if not start_off_timer(timeout, True):
                speech_output = "Wiwo is on, but off timer configuration is wrong. Please validate the cloudwatch event's ID"

    else:
        speech_output = 'Turning wiwo off'
        with OrviboS20() as control:
            resp = control.poweroff(WIWO_ip, WIWO_mac)
        stop_off_timer()

    return build_response(session_attributes, build_speechlet_response(
        card_title, speech_output, reprompt_text, should_end_session))


def handle_timeout():
    print 'handle_timeout'
    with OrviboS20() as control:
        resp = control.poweroff(WIWO_ip, WIWO_mac)
    stop_off_timer()


def build_speechlet_response(title, output, reprompt_text, should_end_session):
    return {
        "outputSpeech": {
            "type": "PlainText",
            "text": output
        },
        "card": {
            "type": "Simple",
            "title": title,
            "content": output
        },
        "reprompt": {
            "outputSpeech": {
                "type": "PlainText",
                "text": reprompt_text
            }
        },
        "shouldEndSession": should_end_session
    }


def build_response(session_attributes, speechlet_response):
    return {
        "version": "1.0",
        "sessionAttributes": session_attributes,
        "response": speechlet_response
    }
