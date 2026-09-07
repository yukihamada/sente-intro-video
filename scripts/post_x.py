#!/usr/bin/env python3
"""Post the intro video to X: chunked media upload (v1.1, OAuth 1.0a user context) → POST /2/tweets with the video →
a reply with the prompt. Standard library only.

  env: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET   (the account that posts; user context, write scope)
  scripts/post_x.py post/x.md out/sente-intro-30s.mp4 [--dry-run]

post/x.md holds the copy: the first section (before a line `---`) is the tweet, the second is the reply.
X counts CJK characters as 2 (weighted length ≤ 280, URLs count 23); the script checks before posting."""
import base64, hashlib, hmac, json, os, pathlib, secrets, sys, time, urllib.parse, urllib.request, urllib.error, re

def oauth_header(method, url, params, body_params=None):
    k, ks, t, ts_ = (os.environ[x] for x in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"))
    oauth = {"oauth_consumer_key": k, "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
             "oauth_timestamp": str(int(time.time())), "oauth_token": t, "oauth_version": "1.0"}
    allp = {**params, **(body_params or {}), **oauth}
    enc = lambda s: urllib.parse.quote(str(s), safe="")
    base = "&".join(f"{enc(a)}={enc(b)}" for a, b in sorted(allp.items()))
    sig_base = "&".join([method.upper(), enc(url), enc(base)])
    key = f"{enc(ks)}&{enc(ts_)}".encode()
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key, sig_base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{enc(a)}="{enc(b)}"' for a, b in sorted(oauth.items()))

def call(method, url, params=None, data=None, headers=None, form=None, json_body=None):
    params = params or {}
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    hdr = {"Authorization": oauth_header(method, url, params, form if form else None), "User-Agent": "sente-intro-video/1"}
    if json_body is not None: data = json.dumps(json_body).encode(); hdr["Content-Type"] = "application/json"
    elif form is not None: data = urllib.parse.urlencode(form).encode(); hdr["Content-Type"] = "application/x-www-form-urlencoded"
    hdr.update(headers or {})
    req = urllib.request.Request(full, data=data, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

def multipart(fields, file_field, file_name, file_bytes):
    b = "----sente" + secrets.token_hex(8); out = bytearray()
    for k, v in fields.items():
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    out += f"--{b}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{file_name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
    out += file_bytes + f"\r\n--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"

def upload_video(path):
    MU = "https://upload.twitter.com/1.1/media/upload.json"
    data = pathlib.Path(path).read_bytes()
    st, r = call("POST", MU, form={"command": "INIT", "media_type": "video/mp4", "total_bytes": len(data), "media_category": "tweet_video"})
    assert st in (200, 201, 202), ("INIT", st, r); mid = r["media_id_string"]
    seg = 4 * 1024 * 1024
    for i in range(0, len(data), seg):
        body, ctype = multipart({"command": "APPEND", "media_id": mid, "segment_index": i // seg}, "media", "chunk", data[i:i + seg])
        st, r = call("POST", MU, data=body, headers={"Content-Type": ctype})
        assert st in (200, 201, 202, 204), ("APPEND", st, r)
    st, r = call("POST", MU, form={"command": "FINALIZE", "media_id": mid}); assert st in (200, 201, 202), ("FINALIZE", st, r)
    info = r.get("processing_info")
    while info and info.get("state") in ("pending", "in_progress"):
        time.sleep(info.get("check_after_secs", 5))
        st, r = call("GET", MU, params={"command": "STATUS", "media_id": mid}); info = r.get("processing_info")
    if info and info.get("state") == "failed": sys.exit("media processing failed: %s" % info)
    return mid

def weighted_len(text):
    t = re.sub(r"https?://\S+", "x" * 23, text)
    return sum(2 if ord(c) > 0x1100 else 1 for c in t)   # CJK & wide → 2, URLs → 23

def load_env():
    """Credentials: env vars, else ~/.config/twitter/.env (X_CONSUMER_KEY/SECRET + X_ACCESS_TOKEN/SECRET as used for @yukihamada)."""
    f = pathlib.Path(os.environ.get("X_ENV_FILE", "~/.config/twitter/.env")).expanduser()
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"'))
    alias = {"X_API_KEY": "X_CONSUMER_KEY", "X_API_SECRET": "X_CONSUMER_SECRET", "X_ACCESS_SECRET": "X_ACCESS_TOKEN_SECRET"}
    for k, v in alias.items():
        if k not in os.environ and v in os.environ: os.environ[k] = os.environ[v]

def main():
    load_env()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; dry = "--dry-run" in sys.argv
    copy, video = pathlib.Path(args[0]).read_text(encoding="utf-8"), args[1]
    parts = [p.strip() for p in copy.split("\n---\n")]; tweet, reply = parts[0], (parts[1] if len(parts) > 1 else "")
    for name, t in (("tweet", tweet), ("reply", reply)):
        if t and weighted_len(t) > 280: sys.exit("%s too long: weighted %d > 280" % (name, weighted_len(t)))
    print("tweet (%d):\n%s\n" % (weighted_len(tweet), tweet)); print("reply (%d):\n%s\n" % (weighted_len(reply), reply))
    if dry: print("dry run: nothing posted"); return
    for v in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"): os.environ[v]  # KeyError early if missing
    mid = upload_video(video); print("media", mid)
    st, r = call("POST", "https://api.x.com/2/tweets", json_body={"text": tweet, "media": {"media_ids": [mid]}}); assert st in (200, 201), (st, r)
    tid = r["data"]["id"]; print("posted https://x.com/i/status/" + tid)
    if reply:
        st, r = call("POST", "https://api.x.com/2/tweets", json_body={"text": reply, "reply": {"in_reply_to_tweet_id": tid}}); assert st in (200, 201), (st, r)
        print("reply https://x.com/i/status/" + r["data"]["id"])

if __name__ == "__main__": main()
