// convert binary to to base64 encoded string
function b2a(a) {
  var c, d, e, f, g, h, i, j, o, b = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=", k = 0, l = 0, m = "", n = [];
  if (!a) return a;
  do c = a.charCodeAt(k++), d = a.charCodeAt(k++), e = a.charCodeAt(k++), j = c << 16 | d << 8 | e,
  f = 63 & j >> 18, g = 63 & j >> 12, h = 63 & j >> 6, i = 63 & j, n[l++] = b.charAt(f) + b.charAt(g) + b.charAt(h) + b.charAt(i); while (k < a.length);
  return m = n.join(""), o = a.length % 3, (o ? m.slice(0, o - 3) :m) + "===".slice(o || 3);
}

// convert base64 encoded string to binary
function a2b(a) {
  var b, c, d, e = {}, f = 0, g = 0, h = "", i = String.fromCharCode, j = a.length;
  for (b = 0; 64 > b; b++) e["ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charAt(b)] = b;
  for (c = 0; j > c; c++) for (b = e[a.charAt(c)], f = (f << 6) + b, g += 6; g >= 8; ) ((d = 255 & f >>> (g -= 8)) || j - 2 > c) && (h += i(d));
  return h;
}

function handler(event) {
    var request = event.request;
    var uri = request.uri;
    var headers = request.headers;

    if (uri.startsWith('/srv/enterprise/')) {
        // Strip off '/srv'. This was the original location I uploaded things to.
        // but it makes more sense for everything to be in the root.
        request.uri = request.uri.substring(4);
    }

    // prefixes that should be swapped on access; used to be done with symlinks on mirror.
    var links = {
        '/pub/openshift-v4/amd64/': '/pub/openshift-v4/x86_64/',
        '/pub/openshift-v4/arm64/': '/pub/openshift-v4/aarch64/',
        '/pub/openshift-v4/clients/': '/pub/openshift-v4/x86_64/clients/',
        '/pub/openshift-v4/dependencies/': '/pub/openshift-v4/x86_64/dependencies/',
    };

    for (var prefix in links) {
        if (request.uri.startsWith(prefix)) {
            request.uri = links[prefix] + request.uri.substring(prefix.length);
        }
    }

    if (!uri.startsWith('/pub') && uri != '/favicon.ico') {

        var unauthorized = {
            statusCode: 401,
            statusDescription: 'Unauthorized',
            headers: {'www-authenticate': {'value': 'Basic'}},
        };

        // Anything not in /pub requires basic auth header
        if (headers == undefined || headers.authorization == undefined) {
            return unauthorized;
        }

        var b64AuthVal = headers.authorization.value.split(' ')[1];  // Strip off "Basic "
        var authVal = a2b(b64AuthVal);
        var username = authVal.substring(0, authVal.indexOf(':'));
        var password = authVal.substring(authVal.indexOf(':')+1);

        var found = false;

        console.log(username)
        if (username == SHARED_USER) {
            if (password == SUPER_SECRET_PASSWORD_SHARED_USER) {
                found = true;
            }
        } else {
            var hash = require('crypto').createHash('sha256')
            var computed_pw = hash.update(SUPER_SECRET_PASSWORD_SEED).update(username).digest('base64')
            if (password == computed_pw) {
                found = true;
            }
        }

        if (!found) {
            return unauthorized;
        }

    }

    // Check whether the URI is missing a file name.
    if (uri.endsWith('/')) {
        request.uri += 'index.html';
    }

    return request;
}