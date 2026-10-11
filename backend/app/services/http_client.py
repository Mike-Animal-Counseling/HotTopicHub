"""HTTPS-only outbound requests that never forward credentials via redirects."""

import ipaddress
from urllib import error, request
from urllib.parse import urlsplit


class NoRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise error.URLError("Outbound redirects are disabled.")


def open_https(req, timeout=8):
    url = req.full_url if isinstance(req, request.Request) else req
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Outbound requests require an HTTPS URL without credentials.")
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise ValueError("Local outbound addresses are not permitted.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private outbound addresses are not permitted.")
    # Destinations come from server-controlled adapters/configuration, never API input.
    return request.build_opener(NoRedirects()).open(req, timeout=timeout)
