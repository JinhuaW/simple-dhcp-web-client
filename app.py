#!/usr/bin/python3
from bottle import route, auth_basic, run, static_file, request
import os
import sys
import subprocess

USERNAME = 'admin'
PASSWORD = 'admin'

DHCPD_LEASES = '/var/lib/dhcp/dhcpd.leases'
DHCPD_CONF = '/etc/dhcp/dhcpd.conf'

# for test
argvs = sys.argv
if len(argvs) == 2:
    DHCPD_LEASES = './test/data/dhcpd.leases'
    DHCPD_CONF = './test/data/dhcpd.conf'

if  'DHCPD_ADMIN_USERNAME' in os.environ:
    USERNAME = os.environ['DHCPD_ADMIN_USERNAME']

if 'DHCPD_ADMIN_PASSWORD' in os.environ:
    PASSWORD = os.environ['DHCPD_ADMIN_PASSWORD']

if  'DHCPD_LEASES_PATH' in os.environ:
    DHCPD_LEASES = os.environ['DHCPD_LEASES_PATH']

if 'DHCPD_CONF_PATH' in os.environ:
    DHCPD_CONF = os.environ['DHCPD_CONF_PATH']


def auth(username, password):
    return username == USERNAME and password == PASSWORD


@route('/admin/addfix', method='POST')
@auth_basic(auth)
def add_fix():
    hostname = request.forms.get('hostname')
    mac = request.forms.get('mac')
    ip = request.forms.get('ip')
    print(hostname, mac, ip)
    add_fix(hostname, mac, ip)
    restart_dhcpd()
    return dict(status=True)


@route('/admin/deletefix', method='POST')
@auth_basic(auth)
def delete_fix():
    host = request.forms.get('hostname')
    mac = request.forms.get('mac')
    delete_fix(host, mac)
    restart_dhcpd()
    return dict(status=True)


@route('/admin/restart', method='POST')
@auth_basic(auth)
def restart_dhcp():
    restart_dhcpd()
    return dict(status=True)


@route('/data.json')
def index():
    free, fixed, staging = parse_dhcp_leases()
    return dict(free=free, fixed=fixed, staging=staging)


@route('/')
def public():
    return static_file('index.html', root='public')


@route('/<filepath:path>')
def server_static(filepath):
    return static_file(filepath, root='public')


def parse_dhcp_leases():
    free  = dict()
    fixed  = dict()
    staging = dict()

    with open(DHCPD_LEASES, 'r') as f:
        for line in f:
            if line.startswith('lease'):
                item = read_lease(f)
                if item['binding'] == 'active':
                    staging[line.split(' ')[1]] = item
                else:
                    free[line.split(' ')[1]] = item

    with open(DHCPD_CONF, 'r') as f:
        for line in f:
            if line.startswith('host'):
                ip = ""
                item = dict(binding='fixed', hostname=line.split(' ')[1])
                for l in f:
                    if l.startswith('}'):
                        break
                    ws = l.split(' ')
                    if ws[2] in 'hardware':
                        item["mac"] = ws[4].replace(';\n', '')
                    elif ws[2] in 'fixed-address':
                        ip = ws[3].replace(';\n', '')
                fixed[ip] = item

    return free, fixed, staging


def read_lease(f):
    d = dict()
    d['has_name'] = False
    for l in f:
        if l.startswith('}'):
            break
        ws = l.split(' ')
        if ws[2] in 'starts':
            d['starts'] =  ws[4].replace(';', '')
        elif ws[2] in 'ends':
            d['ends'] = ws[4].replace(';', '')
        elif ws[2] in 'binding':
            d['binding'] = ws[4].replace(';\n', '')
            if d['binding'] == 'active':
                d['state'] = True
            else:
                d['state'] = False
        elif ws[2] in 'hardware':
            d['mac'] = ws[4].replace(';\n', '')
        elif ws[2] in 'client-hostname':
            d['hostname'] = ws[3].replace(';\n', '').replace('"', '')
    return d


def read_dhcpd_conf():
    lines = []
    with open(DHCPD_CONF, 'r') as f:
        lines = f.readlines()
    return lines


def write_dhcpd_conf(lines):
    with open(DHCPD_CONF, 'w') as f:
        f.writelines(lines)


def add_fix(host, mac, ip):
    lines = read_dhcpd_conf()
    for i, line in enumerate(lines):
        if line.startswith('host'):
            if line.split(' ')[1] == host:
                print ('Duplicated device: ' + host + ' ' + mac + ' ' + ip)
                return
                val = lines[i+1].split(' ')[4].replace(';\n', '')
                if val == mac:
                    return
                val = lines[i+2].split(' ')[3].replace(';\n', '')
                if val == ip:
                    return
    lines.append('host ' + host + ' {\n')
    lines.append('  hardware ethernet ' + mac + ';\n')
    lines.append('  fixed-address ' + ip + ';\n')
    lines.append('}\n')
    write_dhcpd_conf(lines)
    return


def delete_fix(host, mac):
    lines = read_dhcpd_conf()
    for i, line in enumerate(lines):
        if line.startswith('host'):
            if line.split(' ')[1] == host:
                val = lines[i+1].split(' ')[4].replace(';\n', '')
                if val == mac:
                    del lines[i:i+4]
    write_dhcpd_conf(lines)
    return


def restart_dhcpd():
    p = subprocess.Popen('systemctl restart isc-dhcp-server', shell=True,
                         cwd='.',
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         close_fds=True)
    (stdout, stdin, stderr) = (p.stdout, p.stdin, p.stderr)
    if stderr:
        return False
    return True


run(host='0.0.0.0', port=80, debug=False)
