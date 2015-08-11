#!/usr/bin/env python2

from __future__ import print_function
from collections import OrderedDict
from subprocess import call, check_call
from time import sleep, strftime
import fdpexpect
import pxssh
import sys
import argparse
import serial

T1_SYSFS = '/sys/bus/greybus/devices/endo0:1:1:1:13/'
T2_SYSFS = '/sys/bus/greybus/devices/endo0:1:2:1:13/'
T1_CMD = 'loopback_test {} {} 1000 ' + T1_SYSFS + ' /dev/gb/loopback0'
T2_CMD = 'loopback_test sink 512 1000 ' + T2_SYSFS + ' /dev/gb/loopback1'
APB_CMD = 'gbl -t {} -s {} -w 10 -n 10 start'

ROOT_GBL = '/sys/class/gb_loopback'


# default IP of the AP
HOST = '192.168.3.2'
USER = 'root'


SVC_DEFAULT_BAUD = 115200

PWRM_TO_CMDS = (
    ('PWM-G1, 1 lane', ['svc linktest -p 0 -m pwm -g 1 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 1 -s a -l 1']),
    ('PWM-G2, 1 lane', ['svc linktest -p 0 -m pwm -g 2 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 2 -s a -l 1']),
    ('PWM-G3, 1 lane', ['svc linktest -p 0 -m pwm -g 3 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 3 -s a -l 1']),
    ('PWM-G4, 1 lane', ['svc linktest -p 0 -m pwm -g 4 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 4 -s a -l 1']),
    ('PWM-G1, 2 lanes', ['svc linktest -p 0 -m pwm -g 1 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 1 -s a -l 2']),
    ('PWM-G2, 2 lanes', ['svc linktest -p 0 -m pwm -g 2 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 2 -s a -l 2']),
    ('PWM-G3, 2 lanes', ['svc linktest -p 0 -m pwm -g 3 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 3 -s a -l 2']),
    ('PWM-G4, 2 lanes', ['svc linktest -p 0 -m pwm -g 4 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 4 -s a -l 2']),
    ('HS-G1A, 1 lane', ['svc linktest -p 0 -m hs -g 1 -s a -l 1',
                        'svc linktest -p 1 -m hs -g 1 -s a -l 1']),
    ('HS-G2A, 1 lane', ['svc linktest -p 0 -m hs -g 2 -s a -l 1',
                        'svc linktest -p 1 -m hs -g 2 -s a -l 1']),
    ('HS-G1A, 2 lanes', ['svc linktest -p 0 -m hs -g 1 -s a -l 2',
                         'svc linktest -p 1 -m hs -g 1 -s a -l 2']),
    ('HS-G2A, 2 lanes', ['svc linktest -p 0 -m hs -g 2 -s a -l 2',
                         'svc linktest -p 1 -m hs -g 2 -s a -l 2']),
    ('HS-G1B, 1 lane', ['svc linktest -p 0 -m pwm -g 1 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 1 -s a -l 1',
                        'svc linktest -p 0 -m pwm -g 1 -s b -l 1',
                        'svc linktest -p 1 -m pwm -g 1 -s b -l 1',
                        'svc linktest -p 0 -m hs -g 1 -s b -l 1',
                        'svc linktest -p 1 -m hs -g 1 -s b -l 1']),
    ('HS-G2B, 1 lane', ['svc linktest -p 0 -m pwm -g 1 -s a -l 1',
                        'svc linktest -p 1 -m pwm -g 1 -s a -l 1',
                        'svc linktest -p 0 -m pwm -g 1 -s b -l 1',
                        'svc linktest -p 1 -m pwm -g 1 -s b -l 1',
                        'svc linktest -p 0 -m hs -g 2 -s b -l 1',
                        'svc linktest -p 1 -m hs -g 2 -s b -l 1']),
    ('HS-G1B, 2 lanes', ['svc linktest -p 0 -m pwm -g 1 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 1 -s a -l 2',
                         'svc linktest -p 0 -m pwm -g 1 -s b -l 2',
                         'svc linktest -p 1 -m pwm -g 1 -s b -l 2',
                         'svc linktest -p 0 -m hs -g 1 -s b -l 2',
                         'svc linktest -p 1 -m hs -g 1 -s b -l 2']),
    ('HS-G2B, 2 lanes', ['svc linktest -p 0 -m pwm -g 1 -s a -l 2',
                         'svc linktest -p 1 -m pwm -g 1 -s a -l 2',
                         'svc linktest -p 0 -m pwm -g 1 -s b -l 2',
                         'svc linktest -p 1 -m pwm -g 1 -s b -l 2',
                         'svc linktest -p 0 -m hs -g 2 -s b -l 2',
                         'svc linktest -p 1 -m hs -g 2 -s b -l 2']))

#
# UI
#


def info(*args, **kwargs):
    kwargs['file'] = sys.stdout
    print(*args, **kwargs)


def err(*args, **kwargs):
    kwargs['file'] = sys.stderr
    args = ('error:',) + args
    print(*args, **kwargs)


def fatal_err(*args, **kwargs):
    err(*args, **kwargs)
    sys.exit(1)


def svc_io(*args, **kwargs):
    args = ('<SVC>:',) + args
    info(*args, **kwargs)


#
# Command handling
#

def gbl_status(f):

    f.sendline('gbl status')
    f.expect('REQ_PER_SEQ')
    f.expect('nsh>')
    return f.before.split()


def gbl_stats(f, cmd):

    f.sendline('gbl stop')
    f.expect('nsh>')
    info(f.before.strip())

    # split the cmd otherwise, nuttx is missing some
    # characters
    for c in cmd.split():
        f.send(c + ' ')
    f.sendline()
    f.expect('nsh>')
    info(f.before.strip())

    # Wait until completion 'ACTIVE = no'
    while True:
        st = gbl_status(f)
        if st[1] == 'no':
            break
        else:
            sleep(1)

    f.sendline('gbl -f csv status')
    info(f.readline().strip())
    f.readline()
    f.readline()
    f.expect('nsh>')
    info(f.before.strip())

    return f.before.strip()


def exec_svc_cmd(svc, cmd):

    svc.sendline(cmd)
    svc.expect('nsh>')
    info(svc.before.strip())


def exec_loopback(ssh, cmd):

    ssh.sendline(cmd)
    ssh.prompt()
    info(ssh.before.strip())


def run_from_ap(svc, host, test, size, verbose):

    ssh_host = '{}@{}'.format(USER, host)
    csv_path = '~{}/{}_{}_1000.csv'.format(USER, test, size)
    csv_url = '{}:{}'.format(ssh_host, csv_path)

    ap_test_cmd = T1_CMD.format(test, size)

    info(ssh_host, csv_path, csv_url, test, size, ap_test_cmd)

    svcfd = fdpexpect.fdspawn(svc.fd, timeout=5)

    info('Erase previous CSV file ({})'.format(csv_path))

    s = pxssh.pxssh()
    s.login(host, USER)
    s.sendline('rm {}'.format(csv_path))  # run a command
    s.prompt()  # match the prompt
    info(s.before)  # print everything before the prompt.

    count = 1

    try:
        for pwrm, cmds in PWRM_TO_CMDS:

            info('\nTest ({}) - {}\n'.format(count, pwrm))

            for cmd in cmds:
                exec_svc_cmd(svcfd, cmd)

            if verbose:
                # insert the test name into the CSV file
                # TODO: add a new column into the CSV instead of new row
                call(['ssh', ssh_host,
                      'echo "{}" >> {}'.format(pwrm, csv_path)])

            exec_loopback(s, ap_test_cmd)
            exec_loopback(s, ap_test_cmd)
            exec_loopback(s, ap_test_cmd)

            count += 1

    except KeyboardInterrupt:
        info('\nKeyboardInterrupt')

    # transfer the results CSV file to from AP to Host
    call(['scp', csv_url, '.'])
    s.logout()


def run_from_apbridge(svc, host, test, size, verbose, apb):

    csv_path = 'apb_{}_{}_1000.csv'.format(test, size)

    # gbl is using a slightly different name
    apb_test_cmd = APB_CMD.format(test.replace('transfer', 'xfer'), size)

    info(csv_path, test, size, apb_test_cmd)

    svcfd = fdpexpect.fdspawn(svc.fd, timeout=5)

    f = fdpexpect.fdspawn(apb.fd, timeout=5)

    info('Create CSV file ({})'.format(csv_path))

    with open(csv_path, "w") as fd:

        count = 1

        try:
            for pwrm, cmds in PWRM_TO_CMDS:

                info('\nTest ({}) - {}\n'.format(count, pwrm))

                for cmd in cmds:
                    exec_svc_cmd(svcfd, cmd)

                if verbose:
                    # insert the test name into the CSV file
                    # TODO: add a new column into the CSV instead of new row
                    call(['ssh', ssh_host,
                          'echo "{}" >> {}'.format(pwrm, csv_path)])

                fd.write('{},{},{},{}\n'.format(
                          strftime("%c"),
                          test,
                          size,
                          gbl_stats(f, apb_test_cmd)))
                fd.write('{},{},{},{}\n'.format(
                          strftime("%c"),
                          test,
                          size,
                          gbl_stats(f, apb_test_cmd)))
                fd.write('{},{},{},{}\n'.format(
                          strftime("%c"),
                          test,
                          size,
                          gbl_stats(f, apb_test_cmd)))

                count += 1

        except KeyboardInterrupt:
            info('\nKeyboardInterrupt')


def get_devices(ssh):

    ssh.sendline('ls --color=never {}'.format(ROOT_GBL))
    ssh.readline()
    ssh.prompt()

    return ssh.before.split()


def get_device_sysfslink(ssh, dev):

    ssh.sendline('readlink -f {}/{}'.format(ROOT_GBL, dev.replace('!','\!')))
    ssh.readline()
    ssh.prompt()

    return '/'.join(ssh.before.strip().split('/')[:-2])


def get_device_id(ssh, path):

    ssh.sendline('cat {}/../../device_id'.format(path))
    ssh.readline()
    ssh.prompt()

    return ssh.before.strip()


def get_device_path(dev):

     return '/dev/{}'.format(dev.replace('!','/'))


#
# main
#


def main():
    # Parse arguments.
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--baudrate',
                        default=SVC_DEFAULT_BAUD,
                        help='baud rate of SVC/APB tty, default {}'.format(
                            SVC_DEFAULT_BAUD))
    parser.add_argument('svc', help='Path to SVC console tty')
    parser.add_argument('host', help='IP/hostname of target AP', default=HOST)
    parser.add_argument('apb', help='apbridge2 tty', default=None)
    parser.add_argument('-s', '--size', default=512, help='Packet Size')
    parser.add_argument('-t', '--test',
                        default='sink',
                        choices=['sink', 'transfer', 'ping'],
                        help='Test type')
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='Add extra info in CSV')
    parser.add_argument('--ap',
                        action='store_true',
                        help='Run test from AP instead of APBridge')
    parser.add_argument('-l', '--list',
                        action='store_true',
                        help='List loopback devices')
    args = parser.parse_args()


    info('Enumerating loopback devices in the endo...')

    try:
        ssh = pxssh.pxssh()
        ssh.login(args.host, USER)
        devs = get_devices(ssh)
        for dev in devs:
            p = get_device_sysfslink(ssh, dev)
            d = get_device_id(ssh, p)
            info('device_id[{}]={}, dev={}'.format(
                    d, p.split('/')[-1], get_device_path(dev)))
        ssh.logout()
    except:
        fatal_err('failed initializing AP connection through SSH')

    if args.list:
        return

    info('AP host: {}'.format(args.host))

    # Open the SVC and AP console ttys and flush any input characters.
    try:
        info('opening SVC console at: {}, {} baud'.format(
                args.svc, args.baudrate))
        svc = serial.Serial(port=args.svc, baudrate=args.baudrate)
        info('flushing SVC input buffer')
        svc.flushInput()
    except:
        fatal_err('failed initializing SVC')
    try:
        info('opening APBridgeA console at: {}, {} baud'.format(
                args.apb, args.baudrate))
        apb = serial.Serial(port=args.apb, baudrate=args.baudrate)
        info('flushing APBridgeA input buffer')
        apb.flushInput()
    except:
        fatal_err('failed initializing APBridgeA')

    # Execute the above-defined power mode changes at the SVC
    # console.
    if args.ap:
        run_from_ap(svc, args.host, args.test, args.size, args.verbose)
    else:
        run_from_apbridge(svc, args.host, args.test, args.size, args.verbose,
                          apb)

if __name__ == '__main__':
    main()
