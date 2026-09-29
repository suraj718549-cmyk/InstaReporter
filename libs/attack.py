# coding=utf-8
#!/usr/bin/env python3

import re
from requests import Session

from libs.utils import print_success
from libs.utils import print_error
from libs.utils import print_status
from libs.user_agents import get_user_agent

REPORT_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "DNT": "1",
    "Host": "help.instagram.com",
    "Origin": "https://help.instagram.com",
    "Pragma": "no-cache",
    "Referer": "https://help.instagram.com/contact/497253480400030",
}

PROFILE_FORM_URL = "https://help.instagram.com/contact/497253480400030"
VIDEO_FORM_URL   = "https://help.instagram.com/contact/440963189380968"
SUBMIT_URL       = "https://help.instagram.com/ajax/help/contact/submit/page"


def _get_page_tokens(ses, form_url):
    """
    1) Warm up the session via facebook.com (acquires datr/sb cookies required
       by help.instagram.com).
    2) Fetch the Instagram help contact page and extract all CSRF / spin tokens.
    Returns a dict of tokens, or None on failure.
    """
    user_agent = ses.headers.get("User-Agent", "Mozilla/5.0")

    # -- Step 1: Facebook warm-up (Sec-Fetch headers are required for 200) --
    fb_headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }
    try:
        ses.get("https://www.facebook.com/", headers=fb_headers, timeout=15)
    except Exception:
        pass  # non-fatal

    # -- Step 2: Instagram help page --
    help_headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Referer": "https://www.facebook.com/",
    }
    try:
        res = ses.get(form_url, headers=help_headers, timeout=15)
    except Exception as e:
        print_error("Connection error: (PageRequestError)", str(e))
        return None

    if res.status_code != 200:
        print_error("Bad status from help page:", str(res.status_code))
        return None

    text = res.text

    # -- Extract tokens with regex (robust against minor page changes) --
    lsd_m    = re.search(r'\["LSD",\[\],\{"token":"([^"]+)"\}', text)
    spin_r_m = re.search(r'"__spin_r":(\d+)', text)
    spin_b_m = re.search(r'"__spin_b":"([^"]+)"', text)
    spin_t_m = re.search(r'"__spin_t":(\d+)', text)
    hsi_m    = re.search(r'"hsi":"([^"]+)"', text)
    rev_m    = re.search(r'"server_revision":(\d+)', text)

    missing = []
    if not lsd_m:    missing.append("LSD")
    if not spin_r_m: missing.append("spin_r")
    if not spin_b_m: missing.append("spin_b")
    if not spin_t_m: missing.append("spin_t")
    if not hsi_m:    missing.append("hsi")
    if not rev_m:    missing.append("server_revision")

    if missing:
        print_error("Token extraction failed. Missing:", ", ".join(missing))
        return None

    datr = res.cookies.get("datr")
    if not datr:
        print_error("Missing datr cookie from help page.")
        return None

    return {
        "lsd":    lsd_m.group(1),
        "spin_r": spin_r_m.group(1),
        "spin_b": spin_b_m.group(1),
        "spin_t": spin_t_m.group(1),
        "hsi":    hsi_m.group(1),
        "rev":    rev_m.group(1),
        "datr":   datr,
    }


def _make_session(proxy):
    ses = Session()
    user_agent = get_user_agent()
    ses.headers["User-Agent"] = user_agent
    if proxy:
        ses.proxies = {
            "https": "http://" + proxy,
            "http":  "http://" + proxy,
        }
    return ses


def report_profile_attack(username, proxy):
    ses = _make_session(proxy)

    tokens = _get_page_tokens(ses, PROFILE_FORM_URL)
    if tokens is None:
        return

    report_form = {
        "jazoest":                                    "2723",
        "lsd":                                        tokens["lsd"],
        "instagram_username":                         username,
        "Field241164302734019_iso2_country_code":     "US",
        "Field241164302734019":                       "United States",
        "support_form_id":                            "497253480400030",
        "support_form_hidden_fields":                 "{}",
        "support_form_fact_false_fields":             "[]",
        "__user":                                     "0",
        "__a":                                        "1",
        "__dyn":                                      "7xe6Fo4SQ1PyUhxOnFwn84a2i5U4e1Fx-ey8kxx0LxW0DUeUhw5cx60Vo1upE4W0OE2WxO0SobEa81Vrzo5-0jx0Fwww6DwtU6e",
        "__csr":                                      "",
        "__req":                                      "d",
        "__beoa":                                     "0",
        "__pc":                                       "PHASED:DEFAULT",
        "dpr":                                        "1",
        "__rev":                                      tokens["rev"],
        "__s":                                        "5gbxno:2obi73:56i3vc",
        "__hsi":                                      tokens["hsi"],
        "__comet_req":                                "0",
        "__spin_r":                                   tokens["spin_r"],
        "__spin_b":                                   tokens["spin_b"],
        "__spin_t":                                   tokens["spin_t"],
    }

    submit_headers = {
        **REPORT_HEADERS,
        "User-Agent": ses.headers["User-Agent"],
    }

    try:
        res = ses.post(
            SUBMIT_URL,
            data=report_form,
            headers=submit_headers,
            cookies={"datr": tokens["datr"]},
            timeout=15,
        )
    except Exception as e:
        print_error("Connection error: (FormRequestError)", str(e))
        return

    if res.status_code != 200:
        print_error("Report submission failed. Status:", str(res.status_code))
        return

    print_success("Report sent for profile: @" + username)


def report_video_attack(video_url, proxy):
    ses = _make_session(proxy)

    tokens = _get_page_tokens(ses, VIDEO_FORM_URL)
    if tokens is None:
        return

    report_form = {
        "jazoest":                                       "2723",
        "lsd":                                           tokens["lsd"],
        "sneakyhidden":                                  "",
        "Field419623844841592":                          video_url,
        "Field1476905342523314_iso2_country_code":       "US",
        "Field1476905342523314":                         "United States",
        "support_form_id":                               "440963189380968",
        "support_form_hidden_fields":                    '{"423417021136459":false,"419623844841592":false,"754839691215928":false,"1476905342523314":false,"284770995012493":true,"237926093076239":false}',
        "support_form_fact_false_fields":                "[]",
        "__user":                                        "0",
        "__a":                                           "1",
        "__dyn":                                         "7xe6Fo4SQ1PyUhxOnFwn84a2i5U4e1Fx-ey8kxx0LxW0DUeUhw5cx60Vo1upE4W0OE2WxO0SobEa81Vrzo5-0jx0Fwww6DwtU6e",
        "__csr":                                         "",
        "__req":                                         "d",
        "__beoa":                                        "0",
        "__pc":                                          "PHASED:DEFAULT",
        "dpr":                                           "1",
        "__rev":                                         tokens["rev"],
        "__s":                                           "5gbxno:2obi73:56i3vc",
        "__hsi":                                         tokens["hsi"],
        "__comet_req":                                   "0",
        "__spin_r":                                      tokens["spin_r"],
        "__spin_b":                                      tokens["spin_b"],
        "__spin_t":                                      tokens["spin_t"],
    }

    submit_headers = {
        **REPORT_HEADERS,
        "User-Agent": ses.headers["User-Agent"],
        "Referer": VIDEO_FORM_URL,
    }

    try:
        res = ses.post(
            SUBMIT_URL,
            data=report_form,
            headers=submit_headers,
            cookies={"datr": tokens["datr"]},
            timeout=15,
        )
    except Exception as e:
        print_error("Connection error: (FormRequestError)", str(e))
        return

    if res.status_code != 200:
        print_error("Report submission failed. Status:", str(res.status_code))
        return

    print_success("Report sent for video: " + video_url)
