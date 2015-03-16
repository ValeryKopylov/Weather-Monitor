import sys
import getopt
import mysql.connector
import datetime
import time

import matplotlib.pyplot as plt
from spectrum import *
import numpy as np
from scipy import signal


def print_usage():
    print """\
Application arguments:
./display.py
    [-u|--user] <DB login>
    [-p|--p] <DB password>
    [-i|--ip] <DB ip address>
    [-n|--name] <DB schema name>
    [-s|--sensor_id] <sensor id in DB>
    [-f|--date_from] <start date for graph>
    [-t|--date_to] <end date for graph>

Example:
./display.py --user data-collector --password 1 --host_ip 127.0.0.1 --db_name weather_monitor --sensor_id 1 --date_from 2015-01-01 --date_to 2015-02-01
"""


def parse_command_line(arguments):
    user = ''
    password = ''
    host_ip = ''
    db_name = ''
    sensor_id = 0
    date_from = 0
    date_to = 0
    try:
        opts, args = getopt.getopt(
            arguments,
            'hu:p:i:n:s:f:t:',
            ['help', 'user=', 'password=', 'host_ip=', 'db_name=', 'sensor_id=', 'date_from=', 'date_to='])
    except getopt.GetoptError:
        print_usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print_usage()
            sys.exit()
        elif opt in ('-u', '--user'):      user = arg
        elif opt in ('-p', '--password'):  password = arg
        elif opt in ('-i', '--host_ip'):   host_ip = arg
        elif opt in ('-n', '--db_name'):   db_name = arg
        elif opt in ('-s', '--sensor_id'): sensor_id = arg
        elif opt in ('-f', '--date_from'): date_from = arg
        elif opt in ('-t', '--date_to'):   date_to = arg

    if user == '' or password == '' or host_ip == '' or db_name == '' or sensor_id == 0 or date_from == 0 or date_to == 0:
        print_usage()
        sys.exit()

    return user, password, host_ip, db_name, sensor_id, date_from, date_to


def predict(x, P, Fs, Fc):
    #discretization period
    T = np.float128(1 / Fs)

    # total length of output signal
    L = len(x) + P

    # time axis of input + predicted samples
    tp = T * np.linspace(0, L - 1, L)

    # order of regression model
    N = P

    # limit regression order
    if (N < 200):
        N = 200
    if (N > 1000):
        N = 1000

    # design filter using z-transform. we need firwin lowpass filter
    A = 1
    B = signal.firwin(101, cutoff=Fc, window='hamming')

    # apply filter
    x = signal.lfilter(B, A, x)

    # compute regression coefficients.
    # TODO handle rho less than 0 exception. Try to predict by smaller interval in the future
    [A, E, K] = arburg(x, N)

    # allocate memory for output
    y = np.zeros(L)

    # fill part of the output with known part
    y[0:len(x)] = x

    # apply regression model to the signal.
    # actually this is IIR filter.
    # use lfilter func in future.
    for i in range(len(x), L):
        y[i] = -1 * np.sum(np.real(A) * y[i-1:i-1-N:-1])
        
    return tp, y


def main(arguments):
    user, password, host_ip, db_name, sensor_id, date_from, date_to = parse_command_line(arguments)

    t = []
    y = []

    start_time = time.time()
    timestamps = []

    # Connect to DB
    db_connection = mysql.connector.connect(user=user, password=password, host=host_ip, database=db_name)
    cursor = db_connection.cursor()

    # Get measurements from DB
    cursor.execute("""
        SELECT change_time, result
        FROM measurement
        WHERE
            (sensor_id = %s)
            AND
            (change_time BETWEEN %s AND %s)
        ORDER BY change_time
        """, (sensor_id, date_from, date_to))

    fetched = cursor.fetchall()

    # Group fetched data
    for curr_t, curr_y in fetched:
        t.append(curr_t)
        y.append(curr_y)

    plt.close('all')

    # all plots will be there
    fig1 = plt.figure()

    # point where to start prediction
    M = len(y)
    samples_per_day = 5760
    # number of samples in extrapolated time series
    P = len(y) + samples_per_day

    # discretization frequency
    Fs = np.float128(1 / 15.0)

    # discretization period
    T = np.float128(1 / Fs)

    # time axis of input + predicted samples
    ti = T * np.linspace(0, M - 1, M)

    # input signal
    secs_in_day = 86400

    # signal at 1/15/86400 HZ
    # + signal at 1/15/86400/30 HZ
    # + signal at 1/15/86400/30/12 HZ
    # So cutoff can be 1/15/86400 will be ok
    # Cut off frequency for firwin filter
    FC = Fs / secs_in_day * 10 #Hz

    # plot noised guy
    plt.plot(ti, y)

    # create figure for results
    fig2 = plt.figure()
    # do the job
    tp, yp = predict(y, P - M, Fs, FC)

    # plot results
    plt.plot(ti, y, tp, yp)
    # draw current moment
    plt.axvline(M * T, -10, 10, linewidth=4, color='r')
    # show everything
    plt.show()


if __name__ == '__main__':
    main(sys.argv[1:])