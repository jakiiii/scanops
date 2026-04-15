# TLS Hardening

This project expects TLS to be terminated by a reverse proxy or load balancer. Django already supports that model through:

- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- `JTRO_SSL_ENABLED=True` in `core.settings.production`
- secure cookies, HSTS, and HTTPS redirects when production SSL is enabled

## Supported baseline

Use a Mozilla "Intermediate" style policy for public deployments:

- Protocols: `TLSv1.2` and `TLSv1.3` only
- Disable: `SSLv2`, `SSLv3`, `TLSv1.0`, `TLSv1.1`
- Allow only AEAD cipher suites
- Disable weak/legacy suites such as `RC4`, `3DES`, `DES`, `NULL`, `EXPORT`, `MD5`, and static-RSA key exchange suites

That is the safest compatibility baseline for most deployments. If all clients are modern and you control them, a stricter TLS 1.3-only policy can be considered separately.

## Nginx

Use [deploy/nginx/incidentmatrix.conf](/home/jaki/Dev/incidentmatrix/deploy/nginx/incidentmatrix.conf) as the project sample. It now:

- disables old protocols
- limits TLS 1.2 to modern AEAD suites
- relies on TLS 1.3 secure suites only
- disables session tickets
- enables OCSP stapling
- forwards `X-Forwarded-Proto` so Django recognizes HTTPS correctly

## Apache HTTP Server

Example `mod_ssl` baseline:

```apache
SSLProtocol             -all +TLSv1.2 +TLSv1.3
SSLCipherSuite          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
SSLHonorCipherOrder     off
SSLCompression          off
SSLSessionTickets       off
SSLUseStapling          on
SSLStaplingCache        shmcb:/var/run/apache2/ssl_stapling(32768)
RequestHeader set X-Forwarded-Proto "https"
```

## Managed load balancers / CDN TLS termination

If TLS terminates before nginx/apache:

- choose the provider's latest policy that supports only `TLSv1.2` and `TLSv1.3`
- disable legacy compatibility policies
- reject weak suites (`RC4`, `3DES`, `DES`, `NULL`, `EXPORT`, `MD5`, SHA1-only)
- forward `X-Forwarded-Proto: https`
- keep Django production SSL settings enabled

## Django production alignment

For HTTPS deployments, set:

```env
JTRO_ENVIRONMENT=production
JTRO_SSL_ENABLED=True
JTRO_SECURE_SSL_REDIRECT=True
JTRO_SESSION_COOKIE_SECURE=True
JTRO_CSRF_COOKIE_SECURE=True
JTRO_HSTS_SECONDS=31536000
JTRO_HSTS_INCLUDE_SUBDOMAINS=True
JTRO_HSTS_PRELOAD=True
```

## Post-change validation

After updating server config:

1. `python manage.py check --deploy --settings core.settings.production`
2. `nginx -t` or `apachectl configtest`
3. run an external TLS scan against the deployed hostname, such as Mozilla Observatory or SSL Labs
