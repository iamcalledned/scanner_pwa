#!/usr/bin/env python3
"""CLI helper to POST a test push to the running Flask app's immediate send endpoint.

Usage:
    python3 scripts/send_test_push.py --message "hello world"

It posts to /scanner/push/send_now on localhost:5005 by default. Adjust BASE_URL if needed.
"""
import argparse
import requests

BASE_URL = 'http://127.0.0.1:5005'

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--message', '-m', default='Test push from CLI')
    p.add_argument('--url', default=BASE_URL)
    args = p.parse_args()
    r = requests.post(args.url + '/scanner/push/send_now', json={'message': args.message})
    print('status', r.status_code)
    try:
        print(r.json())
    except Exception:
        print(r.text)
