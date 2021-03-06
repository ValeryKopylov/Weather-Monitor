#!/usr/bin/env python

import numpy as np
import matplotlib.pyplot as plt
import sys
import getopt
import mysql.connector
import datetime
import time


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


def plot(fig, xlabel, ylabel, x, y, inc):
    if inc == 1:
        plot.subplot_cntr += 1
    sp = fig.add_subplot(3, 1, plot.subplot_cntr)
    sp.plot(x, y)
    sp.set_xlabel(xlabel)
    sp.set_ylabel(ylabel)


def main(arguments):
    user, password, host_ip, db_name, sensor_id, date_from, date_to = parse_command_line(arguments)

    t = []
    y = []

    t_grouped = []
    y_grouped = []
    intervals_count = 1000

    t_grouped_on_server = []
    y_grouped_on_server = []
    
    start_time = time.time()
    timestamps = []

    # Connect to DB
    db_connection = mysql.connector.connect(user=user, password=password, host=host_ip, database=db_name)
    cursor = db_connection.cursor()
    
    timestamps.append(("Connect to db", time.time()))

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

    timestamps.append(("[group by Python] Execute SELECT", time.time()))

    fetched = cursor.fetchall()

    timestamps.append(("[group by Python] Fetch full data", time.time()))

    # Group fetched data
    interval_length = (datetime.datetime.strptime(date_to, '%Y-%m-%d') - datetime.datetime.strptime(date_from, '%Y-%m-%d')) / intervals_count
    interval_start = 0
    accumulated_y = 0.0
    accumulated_count = 0
    first_point = True
    for curr_t, curr_y in fetched:
        t.append(curr_t)
        y.append(curr_y)
        if first_point:
            first_point = False
            interval_start = curr_t
        if curr_t - interval_start > interval_length:
            if accumulated_count > 0:
                # t_grouped.append(time.mktime(interval_start.timetuple()))
                t_grouped.append(interval_start)
                y_grouped.append(accumulated_y / accumulated_count)
            interval_start += interval_length
            accumulated_y = 0.0
            accumulated_count = 0
        accumulated_y += curr_y
        accumulated_count += 1
    if accumulated_count > 0:
        t_grouped.append(interval_start)
        y_grouped.append(accumulated_y / accumulated_count)

    timestamps.append(("[group by Python] Group and store points", time.time()))

    cursor.callproc("get_measurements", [sensor_id, date_from, date_to, intervals_count])

    timestamps.append(("[group by DB] Execute get_measurements()", time.time()))

    for result in cursor.stored_results():
        fetched = result.fetchall()

    timestamps.append(("[group by DB] Fetch grouped data", time.time()))

    for curr_t, curr_y in fetched:
        t_grouped_on_server.append(curr_t)
        y_grouped_on_server.append(curr_y)

    timestamps.append(("[group by DB] Store grouped points", time.time()))

    plot.subplot_cntr = 0
    plt.close('all')
    fig1 = plt.figure()
    plot(fig1, 'original time', 'signal', t, y, 1)
    plot(fig1, 'grouped time', 'signal', t_grouped, y_grouped, 1)
    plot(fig1, 'server grouped time', 'signal', t_grouped_on_server, y_grouped_on_server, 1)

    timestamps.append(("Build plot", time.time()))

    for timestamp_name, timestamp_value in timestamps:
        print "%s: %f" % (timestamp_name, timestamp_value - start_time)
        start_time = timestamp_value

    plt.show()

if __name__ == '__main__':
    main(sys.argv[1:])
