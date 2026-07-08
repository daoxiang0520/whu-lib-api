/**
 * 在浏览器 Console 中运行，自动拦截 gen + check 请求
 *
 * 使用方法:
 * 1. F12 → Console
 * 2. 粘贴此代码并回车
 * 3. 触发滑块验证码（点预约座位等操作）
 * 4. 脚本会自动捕获并输出两个请求
 */

(function() {
    const origFetch = window.fetch;
    const origXHROpen = XMLHttpRequest.prototype.open;
    const origXHRSend = XMLHttpRequest.prototype.send;

    const captured = [];

    // 拦截 fetch
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        if (url.includes('/cap/cg/')) {
            const body = args[1]?.body;
            console.log(`%c[FETCH] ${url.includes('gen') ? 'GEN' : url.includes('check') ? 'CHECK' : 'CAP'}: ${url}`,
                'color: green; font-weight: bold');
            if (body) console.log('  Body:', typeof body === 'string' ? body.substring(0, 300) : body);

            return origFetch.apply(this, args).then(async (res) => {
                const clone = res.clone();
                const text = await clone.text();
                console.log(`  Response: ${text.substring(0, 500)}`);
                captured.push({url, body, response: text, time: new Date().toISOString()});
                return res;
            });
        }
        return origFetch.apply(this, args);
    };

    // 拦截 XMLHttpRequest
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._url = url;
        this._method = method;
        return origXHROpen.call(this, method, url, ...rest);
    };

    XMLHttpRequest.prototype.send = function(body) {
        if (this._url && this._url.includes('/cap/cg/')) {
            console.log(`%c[XHR ${this._url.includes('gen') ? 'GEN' : this._url.includes('check') ? 'CHECK' : 'CAP'}]: ${this._method} ${this._url}`,
                'color: blue; font-weight: bold');
            if (body) console.log('  Body:', typeof body === 'string' ? body.substring(0, 300) : body);

            this.addEventListener('load', function() {
                console.log(`  Response: ${this.responseText.substring(0, 500)}`);
                captured.push({url: this._url, body, response: this.responseText, time: new Date().toISOString()});
            });
        }
        return origXHRSend.call(this, body);
    };

    console.log('%c✅ 拦截器已激活！现在触发滑块验证码...', 'color: orange; font-size: 14px');
    console.log('%c完成后，在 Console 运行 showCaptured() 查看结果', 'color: orange');

    // 查看捕获结果
    window.showCaptured = function() {
        console.log(`%c=== 捕获到 ${captured.length} 个请求 ===`, 'font-size: 14px');
        captured.forEach((c, i) => {
            const type = c.url.includes('gen') ? 'GEN' : c.url.includes('check') ? 'CHECK' : 'OTHER';
            console.log(`%c[${i+1}] ${type} (${c.time})`, 'font-weight: bold');
            console.log('  URL:', c.url);
            console.log('  Body:', typeof c.body === 'string' ? c.body.substring(0, 500) : JSON.stringify(c.body).substring(0, 500));
            console.log('  Response:', c.response.substring(0, 500));
            console.log('');
        });
        return captured;
    };
})();
