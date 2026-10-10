#!/usr/bin/env python3
"""Mail helper for the pinqloq task runner.

Commands:
  send     Send an HTML mail to the team (To from config.json, CC from machine.json `mail_cc`).

The runner only sends mail; it never reads incoming mail. Decisions come from org members'
issue/PR comments and the owner (panel queue or chat).

The SMTP app password is read from the macOS Keychain, never from files.
"""
import argparse
import email
import email.utils
import json
import mimetypes
import re
import smtplib
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner_config  # noqa: E402

CONFIG = runner_config.read_team_config()
MACHINE_CONFIG = runner_config.read_machine_config()
STATE_DIR = runner_config.STATE_DIR
SENT_LOG_FILE = STATE_DIR / "sent_mails.jsonl"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024



def read_password():
    result = subprocess.run(
        ["security", "find-generic-password", "-a", CONFIG["username"], "-s", CONFIG["keychain_service"], "-w"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit("Keychain entry '%s' not found: %s" % (CONFIG["keychain_service"], result.stderr.strip()))
    return result.stdout.strip()


def attach_file(message, file_path):
    path = Path(file_path)
    size = path.stat().st_size
    if size > MAX_ATTACHMENT_BYTES:
        sys.exit("Attachment too large (%d bytes, limit %d): %s" % (size, MAX_ATTACHMENT_BYTES, path))
    mime_type, _ = mimetypes.guess_type(path.name)
    maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
    message.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)


def command_send(arguments):
    subject = "[%s] %s" % (CONFIG["subject_tag"], arguments.subject) if not arguments.subject.startswith("[") else arguments.subject
    html_body = Path(arguments.html).read_text()
    text_body = Path(arguments.text).read_text() if arguments.text else re.sub(r"<[^>]+>", "", html_body)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email.utils.formataddr((CONFIG["from_name"], CONFIG["from_address"]))
    to_addresses = arguments.to or CONFIG["to"]
    message["To"] = ", ".join(to_addresses)
    cc_addresses = [] if arguments.no_cc else MACHINE_CONFIG["mail_cc"]
    if cc_addresses:
        message["Cc"] = ", ".join(cc_addresses)
    message["Reply-To"] = CONFIG["reply_to"]
    message["Date"] = email.utils.formatdate(localtime=True)
    message_id = email.utils.make_msgid(domain="pinqponq.io")
    message["Message-ID"] = message_id
    if arguments.in_reply_to:
        message["In-Reply-To"] = arguments.in_reply_to
        message["References"] = arguments.in_reply_to
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    for file_path in arguments.attach or []:
        attach_file(message, file_path)

    context = ssl.create_default_context()
    with smtplib.SMTP(CONFIG["smtp_host"], CONFIG["smtp_port"], timeout=60) as server:
        server.starttls(context=context)
        server.login(CONFIG["username"], read_password())
        server.send_message(message, to_addrs=to_addresses + cc_addresses)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_entry = {"message_id": message_id, "subject": subject, "sent_at": datetime.now(timezone.utc).isoformat()}
    with SENT_LOG_FILE.open("a") as log_file:
        log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    print(json.dumps(log_entry, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--html", required=True, help="Path to the HTML body file")
    send_parser.add_argument("--text", help="Path to a plain-text alternative body")
    send_parser.add_argument("--attach", nargs="*", help="Files to attach (screenshots, videos)")
    send_parser.add_argument("--in-reply-to", help="Message-ID to thread under")
    send_parser.add_argument("--no-cc", action="store_true", help="Send only to the To address")
    send_parser.add_argument("--to", nargs="+", help="Override the To addresses from config.json (e.g. a resend to one person)")
    send_parser.set_defaults(handler=command_send)

    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
