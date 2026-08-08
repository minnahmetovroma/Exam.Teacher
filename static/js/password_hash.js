(function () {
    function toHex(bytes) {
        var out = '';
        for (var i = 0; i < bytes.length; i++) {
            var b = bytes[i];
            out += (b < 16 ? '0' : '') + b.toString(16);
        }
        return out;
    }

    function ror(value, amount) {
        return (value >>> amount) | (value << (32 - amount));
    }

    function sha256Fallback(bytes) {
        var h = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
        ];
        var k = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
            0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
            0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
            0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
            0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
            0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
            0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
            0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
            0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
        ];

        var length = bytes.length;
        var bitLenHi = Math.floor(length / 536870912);
        var bitLenLo = (length << 3) >>> 0;
        var msgLen = (((length + 8) >> 6) + 1) << 6;
        var msg = new Uint8Array(msgLen);
        msg.set(bytes);
        msg[length] = 0x80;
        var view = new DataView(msg.buffer);
        view.setUint32(msgLen - 8, bitLenHi);
        view.setUint32(msgLen - 4, bitLenLo);

        for (var off = 0; off < msgLen; off += 64) {
            var w = new Array(64);
            for (var i = 0; i < 16; i++) {
                w[i] = view.getUint32(off + i * 4);
            }
            for (var j = 16; j < 64; j++) {
                var s0 = ror(w[j - 15], 7) ^ ror(w[j - 15], 18) ^ (w[j - 15] >>> 3);
                var s1 = ror(w[j - 2], 17) ^ ror(w[j - 2], 19) ^ (w[j - 2] >>> 10);
                w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0;
            }

            var a = h[0], b = h[1], c = h[2], d = h[3];
            var e = h[4], f = h[5], g = h[6], hh = h[7];

            for (var t = 0; t < 64; t++) {
                var bigS1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25);
                var ch = (e & f) ^ (~e & g);
                var t1 = (hh + bigS1 + ch + k[t] + w[t]) >>> 0;
                var bigS0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22);
                var maj = (a & b) ^ (a & c) ^ (b & c);
                var t2 = (bigS0 + maj) >>> 0;
                hh = g; g = f; f = e; e = (d + t1) >>> 0;
                d = c; c = b; b = a; a = (t1 + t2) >>> 0;
            }

            h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0;
            h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
            h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0;
            h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
        }

        var out = new Uint8Array(32);
        for (var i = 0; i < 8; i++) {
            out[i * 4] = (h[i] >>> 24) & 0xff;
            out[i * 4 + 1] = (h[i] >>> 16) & 0xff;
            out[i * 4 + 2] = (h[i] >>> 8) & 0xff;
            out[i * 4 + 3] = h[i] & 0xff;
        }
        return out;
    }

    async function sha256hex(str) {
        var data = new TextEncoder().encode(str);
        if (window.crypto && window.crypto.subtle) {
            var buffer = await window.crypto.subtle.digest('SHA-256', data);
            return toHex(new Uint8Array(buffer));
        }
        return toHex(sha256Fallback(data));
    }

    function moveToHidden(field, digest) {
        var hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = field.name;
        hidden.value = digest;
        field.form.appendChild(hidden);
        field.removeAttribute('name');
        field.value = '';
    }

    function init() {
        var passwordInput = document.getElementById('password');
        if (!passwordInput || !passwordInput.form) {
            return;
        }
        var form = passwordInput.form;
        var emailInput = document.getElementById('email');

        form.addEventListener('submit', function (event) {
            if (form.dataset.hashed) {
                return;
            }
            event.preventDefault();

            var email = emailInput ? emailInput.value : '';
            var repeatInput = document.getElementById('password_repeat');

            var tasks = [sha256hex(email + ':' + passwordInput.value)];
            if (repeatInput) {
                tasks.push(sha256hex(email + ':' + repeatInput.value));
            }

            Promise.all(tasks).then(function (digests) {
                moveToHidden(passwordInput, digests[0]);
                if (repeatInput) {
                    moveToHidden(repeatInput, digests[1]);
                }
                form.dataset.hashed = '1';
                form.submit();
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
