import concurrent.futures
from datetime import datetime
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

# ---------------------------------------------------------
# Environment Parsers & Configuration
# ---------------------------------------------------------
def parse_range(var_name: str, default_min: float, default_max: float):
    raw_val = os.getenv(var_name, "").strip()
    if not raw_val:
        return default_min, default_max
    try:
        parts = [p.strip() for p in raw_val.split(",") if p.strip()]
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
        elif len(parts) == 1:
            val = float(parts[0])
            return val, val
    except ValueError:
        print(f"[WARN] Invalid range in '{var_name}' ('{raw_val}'). Using defaults ({default_min}, {default_max}).")
    return default_min, default_max


def parse_referrers(var_name: str, defaults: list):
    raw_val = os.getenv(var_name, "")
    if not raw_val.strip():
        return defaults
    items = [item.strip() for item in raw_val.split(",")]
    return items if items else defaults


def parse_list(var_name: str, defaults: list):
    raw_val = os.getenv(var_name, "").strip()
    if not raw_val and not var_name.endswith("S"):
        raw_val = os.getenv(f"{var_name}S", "").strip()
    elif not raw_val and var_name.endswith("S"):
        raw_val = os.getenv(var_name[:-1], "").strip()

    if not raw_val:
        return defaults
    items = [item.strip() for item in raw_val.split(",") if item.strip()]
    return items if items else defaults


# ---------------------------------------------------------
# Realistic User-Agent Pools (Varied OS & Browser Versions)
# ---------------------------------------------------------
# Windows 10 & 11 across Chrome, Edge, and Firefox (v140-151)
WINDOWS_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
]

# macOS: Sequoia (15.x), Sonoma (14.x), and Ventura (13.x)
MAC_UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
]

# Linux Desktop (Ubuntu, Fedora, generic x86_64)
LINUX_UAS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
]

# iPhone across iOS 18, 17, and 16
IPHONE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/150.0.0.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/146.0.0.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/148.0 Mobile/15E148 Safari/605.1.15"
]

# Android across versions 15, 14, 13, and 12 on Samsung, Pixel, OnePlus, Xiaomi
ANDROID_UAS = [
    # Android 15 - Google Pixel 9 Pro
    "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Mobile Safari/537.36",
    # Android 14 - Samsung Galaxy S24 Ultra
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    # Android 14 - Google Pixel 8
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36",
    # Android 13 - Samsung Galaxy S23
    "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
    # Android 13 - Xiaomi 13 Pro
    "Mozilla/5.0 (Linux; Android 13; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Mobile Safari/537.36",
    # Android 12 - Samsung Galaxy S22
    "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
    # Android 14 - OnePlus 12
    "Mozilla/5.0 (Linux; Android 14; CPH2573) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    # Android 14 - Samsung Browser on Galaxy A55
    "Mozilla/5.0 (Linux; Android 14; SM-A556B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36"
]

# Custom User-Agent lists if provided
CUSTOM_DESKTOP_UAS = parse_list("DESKTOP_USER_AGENTS", [])
CUSTOM_MOBILE_UAS = parse_list("MOBILE_USER_AGENTS", [])


def pick_desktop_ua():
    """66% Windows, 30% macOS, 4% Linux."""
    if CUSTOM_DESKTOP_UAS:
        return random.choice(CUSTOM_DESKTOP_UAS), "Custom-Desktop"

    roll = random.random()
    if roll < 0.04:  # Exactly 4% Linux
        return random.choice(LINUX_UAS), "Linux"
    elif roll < 0.34:  # 30% macOS
        return random.choice(MAC_UAS), "macOS"
    else:  # 66% Windows
        return random.choice(WINDOWS_UAS), "Windows"


def pick_mobile_ua():
    """40% iPhone (iOS), 60% Android."""
    if CUSTOM_MOBILE_UAS:
        return random.choice(CUSTOM_MOBILE_UAS), "Custom-Mobile"

    if random.random() < 0.40:  # 40% iPhone
        return random.choice(IPHONE_UAS), "iOS"
    else:  # 60% Android
        return random.choice(ANDROID_UAS), "Android"


# ---------------------------------------------------------
# Environment Variables & Defaults
# ---------------------------------------------------------
RAW_KEYS = os.getenv(
    "API_KEYS",
    os.getenv("SCRAPERAPI_KEYS", os.getenv("SCRAPINGANT_API_KEYS", "Key1:081130f37f19d409c438e3b29a73421c"))
)

WORKER_MIN, WORKER_MAX = parse_range("WORKER_COUNT_RANGE", 5, 7)
GAP_MIN, GAP_MAX = parse_range("WORKER_GAP_RANGE", 8.0, 12.0)
CYCLE_MIN, CYCLE_MAX = parse_range("CYCLE_INTERVAL_RANGE", 50.0, 70.0)

# Browser Rendering Toggle ("true" or "false")
BROWSER_RENDERING = os.getenv("BROWSER_RENDERING", "true").strip().lower()

# Device Types: Reads DEVICE_TYPE or DEVICE_TYPES
DEFAULT_DEVICES = ["desktop", "mobile"]
DEVICE_TYPES = [d.lower() for d in parse_list("DEVICE_TYPE", DEFAULT_DEVICES)]

# Referrers (Includes "none" for direct traffic)
DEFAULT_REFERRERS = [
    "none",
    "https://app.bullpen.fi/",
    "https://bullpen.fi/",
    "https://www.google.com/",
    "https://www.facebook.com/"
]
REFERRERS = parse_referrers("REFERRERS", DEFAULT_REFERRERS)

# Target URLs / Slugs
DEFAULT_SLUGS = [
    "jack", "6DNUvqf", "652HU1t", "tzlMgCf", "fNPZlqT",
    "bTi9oJs", "QMOvAAL", "OVMrJe2", "VQH8P3L", "xDVN1Bq", "CLfcNh1"
]
SLUGS = parse_list("TARGET_SLUGS", DEFAULT_SLUGS)
CUSTOM_DIRECT_URLS = parse_list("TARGET_URLS", [])

# Supported ScraperAPI Country Codes
TIER_1 = [
    ("FR", "fr"), ("DE", "de"), ("NL", "nl"), ("ES", "es"),
    ("IT", "it"), ("PL", "pl"), ("SE", "se"), ("BR", "br"),
    ("KR", "kr"), ("TR", "tr"), ("VN", "vn"), ("ID", "id"),
    ("CA", "ca"), ("JP", "jp"), ("SG", "sg")
]
TIER_2 = [
    ("US", "us"), ("GB", "gb"), ("CZ", "cz"), ("RO", "ro"),
    ("AE", "ae"), ("MX", "mx"), ("TH", "th"), ("PH", "ph")
]
TIER_3 = [
    ("IN", "in"), ("SA", "sa"), ("HK", "hk"), ("TW", "tw")
]


# ---------------------------------------------------------
# Key Structure & Manager
# ---------------------------------------------------------
class ManagedKey:
    def __init__(self, name: str, token: str):
        self.name = name.strip()
        self.token = token.strip()
        if len(self.token) >= 8:
            self.masked = f"{self.token[:4]}...{self.token[-4:]}"
        else:
            self.masked = self.token
        self.tag = f"{self.name} [{self.masked}]"


class KeyPoolManager:
    def __init__(self, raw_str: str):
        self.active_keys = []
        self.dead_keys = []
        self.index = 0

        entries = [k.strip() for k in raw_str.split(",") if k.strip()]
        for idx, entry in enumerate(entries, start=1):
            if ":" in entry:
                name, token = entry.split(":", 1)
                self.active_keys.append(ManagedKey(name, token))
            else:
                self.active_keys.append(ManagedKey(f"Key#{idx}", entry))

    def get_key(self) -> ManagedKey:
        if not self.active_keys:
            return None
        key = self.active_keys[self.index % len(self.active_keys)]
        self.index = (self.index + 1) % len(self.active_keys)
        return key

    def mark_dead(self, key_obj: ManagedKey, reason: str):
        if key_obj in self.active_keys:
            self.active_keys.remove(key_obj)
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            self.dead_keys.append((key_obj, reason, ts))

            print("\n" + "#" * 70)
            print(f" [PINNED ALERT] API KEY DIED / EXHAUSTED CREDITS")
            print(f"  Key Identifier : {key_obj.tag}")
            print(f"  Death Time     : {ts}")
            print(f"  Confirmed Cause: {reason}")
            print(f"  Active Remaining: {len(self.active_keys)} key(s)")
            print("#" * 70 + "\n")

    def print_pinned_status(self):
        if not self.dead_keys:
            return
        print("-" * 70)
        print(" [PINNED AUDIT] PERMANENTLY DEAD KEYS:")
        for k_obj, reason, ts in self.dead_keys:
            print(f"  -> {k_obj.tag} | Died: {ts} | Reason: {reason}")
        print("-" * 70)


pool = KeyPoolManager(RAW_KEYS)


# ---------------------------------------------------------
# Dynamic Links & Routing
# ---------------------------------------------------------
def generate_cycle_links(worker_count: int):
    tasks = []
    if CUSTOM_DIRECT_URLS:
        sample_size = min(worker_count, len(CUSTOM_DIRECT_URLS))
        chosen_urls = random.sample(CUSTOM_DIRECT_URLS, sample_size)
        for url in chosen_urls:
            tasks.append((url, "custom", "CUSTOM (URL)"))
        return tasks

    selected_slugs = random.sample(SLUGS, min(worker_count, len(SLUGS)))
    for slug in selected_slugs:
        if random.random() < 0.86:
            url = f"https://app.bullpen.fi?via={slug}"
            ltype = "VIA (?)"
        else:
            url = f"https://go.bullpen.fi/{slug}"
            ltype = "DIRECT (/)"
        tasks.append((url, slug, ltype))
    return tasks


def pick_country():
    roll = random.random()
    if roll < 0.50:
        return "T1", *random.choice(TIER_1)
    elif roll < 0.85:
        return "T2", *random.choice(TIER_2)
    else:
        return "T3", *random.choice(TIER_3)


# ---------------------------------------------------------
# Worker Bot Task (ScraperAPI Engine)
# ---------------------------------------------------------
def execute_bot(bot_id: int, total_bots: int, target_url: str, slug: str, ltype: str, stagger_delay: float):
    time.sleep(stagger_delay)

    key_obj = pool.get_key()
    if not key_obj:
        return

    tier, label, code = pick_country()
    chosen_device = random.choice(DEVICE_TYPES)

    # Pick specific UA and OS
    if chosen_device == "mobile":
        selected_ua, os_label = pick_mobile_ua()
    else:
        chosen_device = "desktop"
        selected_ua, os_label = pick_desktop_ua()

    # ScraperAPI query parameters
    params = {
        "api_key": key_obj.token,
        "device_type": chosen_device,
        "country_code": code,
        "render": BROWSER_RENDERING,
        "keep_headers": "true",
        "url": target_url
    }

    url = f"http://api.scraperapi.com?{urllib.parse.urlencode(params)}"
    
    headers = {
        "User-Agent": selected_ua
    }

    chosen_referrer = random.choice(REFERRERS)
    if chosen_referrer and chosen_referrer.lower() not in ("none", "direct", "empty"):
        headers["Referer"] = chosen_referrer
        ref_display = chosen_referrer
    else:
        ref_display = "None (Direct)"

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=65) as resp:
            print(f"[Bot-{bot_id}/{total_bots}] [{tier}-{label}] [{chosen_device.upper()}:{os_label}] [{ltype} {slug}] [Ref: {ref_display}] [{key_obj.tag}] -> HTTP {resp.status} OK")

    except urllib.error.HTTPError as e:
        raw_detail = e.read().decode("utf-8", errors="ignore")[:70].strip()

        if e.code in (401, 403):
            reason_msg = f"HTTP {e.code} Credits Exhausted / Invalid ScraperAPI Key ({raw_detail})"
            pool.mark_dead(key_obj, reason_msg)
        elif e.code == 429:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 429 Rate limit exceeded: {raw_detail}")
        elif e.code == 404:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 404 Route unreachable: {raw_detail}")
        elif e.code == 500:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [TRANSIENT] HTTP 500 ScraperAPI upstream error: {raw_detail}")
        else:
            print(f"[Bot-{bot_id}] [{key_obj.tag}] [WARNING] HTTP {e.code}: {raw_detail}")

    except Exception as ex:
        print(f"[Bot-{bot_id}] [{key_obj.tag}] [CLIENT ERROR]: {str(ex)}")

    time.sleep(random.uniform(GAP_MIN, GAP_MAX))


# ---------------------------------------------------------
# Engine Main Loop
# ---------------------------------------------------------
def main():
    print("==================================================")
    print("   SCRAPER ENGINE INITIALIZED (RAILWAY/RENDER)    ")
    print("==================================================")
    print(f"Total Active Keys    : {len(pool.active_keys)}")
    print(f"Browser Rendering    : {BROWSER_RENDERING}")
    print(f"Device Types Allowed : {DEVICE_TYPES}")
    print(f"Desktop Routing      : 66% Windows, 30% macOS (13-15), 4% Linux")
    print(f"Mobile Routing       : 40% iPhone (iOS 16-18), 60% Android (12-15)")
    print(f"Configured Referrers : {len(REFERRERS)} options (including direct/none)")
    print(f"Workers Per Cycle    : {int(WORKER_MIN)} - {int(WORKER_MAX)}")
    print(f"Worker Gap Range     : {GAP_MIN:.1f}s - {GAP_MAX:.1f}s")
    print(f"Cycle Duration Range : {CYCLE_MIN:.1f}s - {CYCLE_MAX:.1f}s")
    if CUSTOM_DIRECT_URLS:
        print(f"Target Mode          : Custom URLs ({len(CUSTOM_DIRECT_URLS)} targets)")
    else:
        print(f"Target Mode          : Slugs ({len(SLUGS)} targets)")
    print("==================================================\n")

    cycle_num = 1

    try:
        while True:
            if not pool.active_keys:
                print("\n" + "!" * 70)
                print(" [SHUTDOWN] ALL CONFIGURED KEYS ARE COMPLETELY DEAD / EXHAUSTED.")
                pool.print_pinned_status()
                print(" Process exiting now. Update API_KEYS to resume.")
                print("!" * 70 + "\n")
                sys.exit(0)

            cycle_start = time.time()
            worker_count = random.randint(int(WORKER_MIN), int(WORKER_MAX))
            target_cycle_time = random.uniform(CYCLE_MIN, CYCLE_MAX)

            print(f"\n--- [Cycle #{cycle_num}] Starting {worker_count} bots | Target: {target_cycle_time:.1f}s | Active Keys: {len(pool.active_keys)} ---")

            tasks = generate_cycle_links(worker_count)

            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = []
                for idx, (url, slug, ltype) in enumerate(tasks):
                    stagger = idx * random.uniform(GAP_MIN, GAP_MAX)
                    futures.append(
                        executor.submit(execute_bot, idx + 1, worker_count, url, slug, ltype, stagger)
                    )
                concurrent.futures.wait(futures)

            elapsed = time.time() - cycle_start
            wait_time = target_cycle_time - elapsed

            pool.print_pinned_status()

            if wait_time > 0 and pool.active_keys:
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Pausing {wait_time:.1f}s before next round ---")
                time.sleep(wait_time)
            elif pool.active_keys:
                print(f"--- [Cycle #{cycle_num} Complete] Elapsed: {elapsed:.1f}s | Starting next round immediately ---")

            cycle_num += 1

    except KeyboardInterrupt:
        print("\nTermination signal received. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()