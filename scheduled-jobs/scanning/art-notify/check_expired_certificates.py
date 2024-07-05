"""
This script is to check if the certificates are valid for a list of urls and notify in Slack if the certificate is going to expire in 30 days.
"""
import ssl
import socket
from datetime import datetime, timedelta


def get_certificate_expiry_date(hostname):
    """Get the SSL certificate expiry date for a given hostname."""
    context = ssl.create_default_context()
    conn = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=hostname)

    # Connect to the server
    conn.settimeout(3.0)
    conn.connect((hostname, 443))
    cert = conn.getpeercert()

    # Extract the expiry date
    expiry_date_str = cert['notAfter']
    expiry_date = datetime.strptime(expiry_date_str, '%b %d %H:%M:%S %Y %Z')

    conn.close()

    return expiry_date


def check_url(host_name, days_in_advance=30):
    """Check a URL and notify if their SSL certificate expires within a given number of days."""
    notification_threshold = datetime.now() + timedelta(days=days_in_advance)
    expiry_date = get_certificate_expiry_date(host_name)

    if expiry_date < notification_threshold:
        return f"ALERT: The SSL certificate for {host_name} will expire on {expiry_date}"
    else:
        return None


def check_expired_certificates():
    # List of URLs to check
    urls = [
        "art-dash.engineering.redhat.com",
    ]

    expired_certificates = []

    for url in urls:
        status = check_url(url)
        if status:
            expired_certificates.append(status)

    return "\n".join(expired_certificates) if expired_certificates else None
