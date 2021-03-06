import socket
import ssl
import sys
from thread import *
import psutil
import platform

from processes import LinuxSensor, WindowsSensor, MacOSSensor, GenericSensor
import signal
from utils import sanitizer, SecureSocket

HOST = ''  # All interfaces
PORT = 2017
modes = {'get_pid': 'get_pid', 'kill_pid': 'kill_pid'}

# Platform systems
LINUX = 'Linux'
WINDOWS = 'Windows'
MAC = 'Darwin'

# SSL CERTS
SENSOR_CERT_FILE = 'misc/cert_sensor.pem'
SENSOR_KEY_FILE = 'misc/key_sensor.pem'
SERVER_CERT_FILE = 'misc/server.pem'


class ProcessSensor:
    def __init__(self):
        self.sensor = get_specific_sensor()
        self.secure_socket = SecureSocket(SecureSocket.SERVER, server_cert=SENSOR_CERT_FILE,
                                          client_cert=SERVER_CERT_FILE, server_key=SENSOR_KEY_FILE)

    def start(self):
        """
        Listens for a request, process it and replies with the corresponding PID or killing the specific PID
        """

        self._hook_termination_handler()
        self.secure_socket.bind(HOST, PORT)

        while True:
            try:
                connection = self.secure_socket.wait_connection()
            except socket.error:
                continue

            start_new_thread(self._deal_with_client, (connection,))

        self.secure_socket.close()

    def _deal_with_client(self, connection):
        while True:
            data = connection.recv(1024)
            if not data:
                break

            reply = process_received_data(data, self.sensor)
            connection.send(reply)

        connection.close()

    def _termination_handler(self, signum, frame):
        """
         If the process is terminated, sensor.close will be called
        """
        print '[i] Shutting down...'
        self.sensor.close()
        sys.exit(1)

    def _hook_termination_handler(self):
        signal.signal(signal.SIGTERM, self._termination_handler)
        signal.signal(signal.SIGINT, self._termination_handler)


def get_specific_sensor():
    """
    :return: Platform specific sensor, if there is any problem initializing the sensor, the generic one will be return
    """
    system = platform.system()

    if system == LINUX:
        return LinuxSensor()
    elif system == WINDOWS:
        return WindowsSensor()
    elif system == MAC:
        return MacOSSensor()
    else:
        return GenericSensor()


def process_received_data(data, sensor):
    split_data = data.rstrip().split(',')
    mode = split_data[0]

    if mode == modes['get_pid']:
        reply = _get_pid(split_data[1:], sensor)
    elif mode == modes['kill_pid']:
        reply = _kill_pid(split_data[1:])
    else:
        reply = '-1, no correct mode'

    return reply


def _get_pid(split_data, sensor):
    """
    Uses the sensor to retrieve the PID and process name
    :param split_data: Data representing the request fields.
                       Example: get_pid,udp,192.168.0.200,8080,2017-07-03 23:29:32.689208
    :param sensor: Sensor to be used
    :return: PID and proccess name. Example: 1298,Firefox
    """
    prot, ip_dst, port_dst, timestamp = split_data
    prot = prot.lower()

    if not sanitizer.check_get_pid_params(prot, ip_dst, port_dst, timestamp):
        return '-1,error checking input'

    return sensor.search_process(prot, ip_dst, port_dst, timestamp)


def _kill_pid(split_data):
    """
    :param split_data: Data representing the request fields. Example: kill_pid,1987,Firefox
    :return error or successful
    """
    pid = split_data[0]
    error = 'error'

    if not sanitizer.check_kill_pid_params(pid):
        return 'error checking input'

    try:
        p = psutil.Process(int(pid))
        p.kill()
        return 'correct'

    except:
        return error


if __name__ == '__main__':
    process_sensor = ProcessSensor()
    process_sensor.start()
