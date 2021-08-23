function b2a(a) {
  var c, d, e, f, g, h, i, j, o, b = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=", k = 0, l = 0, m = "", n = [];
  if (!a) return a;
  do c = a.charCodeAt(k++), d = a.charCodeAt(k++), e = a.charCodeAt(k++), j = c << 16 | d << 8 | e,
  f = 63 & j >> 18, g = 63 & j >> 12, h = 63 & j >> 6, i = 63 & j, n[l++] = b.charAt(f) + b.charAt(g) + b.charAt(h) + b.charAt(i); while (k < a.length);
  return m = n.join(""), o = a.length % 3, (o ? m.slice(0, o - 3) :m) + "===".slice(o || 3);
}

function handler(event) {
    var request = event.request;
    var uri = request.uri;
    var headers = request.headers;

    var authUser = '*******************************************REDACTED********************************************';
    var authPass = '*******************************************REDACTED********************************************';
    var authString = 'Basic ' + b2a(authUser + ':' + authPass)

    if (uri.startsWith('/srv/enterprise/')) {
        // Strip off '/srv'. This was the original location I uploaded things to.
        // but it makes more sense for everything to be in the root.
        request.uri = request.uri.substring(4)
    }

    if (!uri.startsWith('/pub')) {
        // Anything not in /pub requires basic auth
        if (headers == undefined || headers.authorization == undefined || headers.authorization.value.indexOf(authString) < 0) {
            var response = {
                statusCode: 401,
                statusDescription: 'Unauthorized',
                headers: {},
            };
            response.headers['www-authenticate'] = {'value': 'Basic'};
            return response;
        }
    }

    // Check whether the URI is missing a file name.
    if (uri.endsWith('/')) {
        request.uri += 'index.html';
    }

    return request;
}