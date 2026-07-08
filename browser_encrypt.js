/**
 * 浏览器 Console 中运行 — 使用页面自带的 CryptoJS + JSEncrypt 加密
 *
 * 用法:
 *   1. 打开页面，确保 TAC SDK 已加载
 *   2. 打开验证码弹窗 (触发 openCaptcha，确保密钥已更新)
 *   3. 在 Console 中先粘贴此文件
 *   4. 调用 encryptForCheck(captchaId, offsetX) 生成加密 payload
 */

// 获取当前页面加载的加密库
const CryptoJSLib = window.CryptoJS;
const JSEncryptLib = window.JSEncrypt;

function randomHex(n) {
    return Array.from({length: n}, () =>
        Math.floor(Math.random() * 256).toString(16).padStart(2, '0')
    ).join('');
}

function encryptPayload(plainData, plainCustom) {
    const skHex = randomHex(16);
    const ivHex = randomHex(16);

    const skWA = CryptoJSLib.enc.Hex.parse(skHex);
    const ivWA = CryptoJSLib.enc.Hex.parse(ivHex);

    const dataJson = JSON.stringify(plainData);
    const customJson = JSON.stringify(plainCustom);

    // AES-CTR encrypt data
    const encData = CryptoJSLib.AES.encrypt(
        CryptoJSLib.enc.Utf8.parse(dataJson),
        skWA,
        { iv: ivWA, mode: CryptoJSLib.mode.CTR, padding: CryptoJSLib.pad.NoPadding }
    );

    // AES-CTR encrypt custom
    const encCustom = CryptoJSLib.AES.encrypt(
        CryptoJSLib.enc.Utf8.parse(customJson),
        skWA,
        { iv: ivWA, mode: CryptoJSLib.mode.CTR, padding: CryptoJSLib.pad.NoPadding }
    );

    const dataB64 = encData.ciphertext.toString(CryptoJSLib.enc.Base64);
    const customB64 = encCustom.ciphertext.toString(CryptoJSLib.enc.Base64);

    // RSA encrypt key|iv using TAC's current public key
    const jsEncrypt = new JSEncryptLib();
    jsEncrypt.setPublicKey(TAC.enc.rsaPublicKey);
    const ki = jsEncrypt.encrypt(skHex + '|' + ivHex);

    return {
        data: dataB64,
        custom: customB64,
        ki: ki,
        _debug: { skHex, ivHex }
    };
}

/**
 * 生成 check 请求的加密 payload
 * @param {string} captchaId - gen 返回的 captcha ID
 * @param {number} offsetX - 滑块偏移量
 * @returns {object} 可直接用于 fetch POST 的 body
 */
window.encryptForCheck = function(captchaId, offsetX) {
    const now = Date.now();
    const plainData = {
        bgImageWidth: 600,
        bgImageHeight: 360,
        sliderImageWidth: 110,
        sliderImageHeight: 360,
        startSlidingTime: now,
        endSlidingTime: now + 1500,
        trackList: [
            {x: 0, y: 0, t: 0},
            {x: Math.round(offsetX * 0.3), y: 1, t: 400},
            {x: Math.round(offsetX * 0.7), y: -1, t: 900},
            {x: offsetX, y: 0, t: 1500}
        ]
    };

    const plainCustom = {
        username: JSON.parse(sessionStorage.getItem('jsq_p-userInfo')).username,
        session: { current_window_url: window.location.origin + window.location.pathname }
    };

    const encrypted = encryptPayload(plainData, plainCustom);
    const payload = {
        id: captchaId,
        data: encrypted.data,
        custom: encrypted.custom,
        ki: encrypted.ki
    };

    console.log('=== 加密完成 ===');
    console.log('Payload:', JSON.stringify(payload));
    console.log('');
    console.log('curl 命令 (复制到终端执行):');
    console.log('curl -k -X POST https://seat.lib.whu.edu.cn/jsq/static/cap/cg/check \\');
    console.log('  -H "Content-Type: application/json;charset=UTF-8" \\');
    console.log('  -H "User-Agent: Mozilla/5.0" \\');
    console.log('  -b "jsq_JSESSIONID=' + document.cookie.match(/jsq_JSESSIONID=([^;]+)/)[1] + '" \\');
    console.log('  -d \\\'' + JSON.stringify(payload) + '\\\'');

    return payload;
};

/**
 * 发起加密 gen 请求
 * @returns {Promise<string>} captcha ID
 */
window.encryptGen = async function() {
    const skHex = randomHex(16);
    const ivHex = randomHex(16);

    const custom = JSON.stringify({
        username: JSON.parse(sessionStorage.getItem('jsq_p-userInfo')).username,
        session: { current_window_url: window.location.origin + window.location.pathname }
    });

    const skWA = CryptoJSLib.enc.Hex.parse(skHex);
    const ivWA = CryptoJSLib.enc.Hex.parse(ivHex);
    const encCustom = CryptoJSLib.AES.encrypt(
        CryptoJSLib.enc.Utf8.parse(custom),
        skWA,
        { iv: ivWA, mode: CryptoJSLib.mode.CTR, padding: CryptoJSLib.pad.NoPadding }
    );
    const customB64 = encCustom.ciphertext.toString(CryptoJSLib.enc.Base64);

    const jsEncrypt = new JSEncryptLib();
    jsEncrypt.setPublicKey(TAC.enc.rsaPublicKey);
    const ki = jsEncrypt.encrypt(skHex + '|' + ivHex);

    const body = JSON.stringify({ custom: customB64, ki: ki });

    const resp = await fetch('/jsq/static/cap/cg/gen/SLIDER', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json;charset=UTF-8' },
        body: body
    });
    const result = await resp.json();
    console.log('Gen result:', result);
    if (result.captcha && result.captcha.type === 'SLIDER') {
        console.log('Captcha ID:', result.id);
        return result.id;
    }
    return null;
};

console.log('✅ browser_encrypt.js 已加载');
console.log('使用方法:');
console.log('  encryptGen() - 加密 gen 请求');
console.log('  encryptForCheck(captchaId, offsetX) - 加密 check 请求');
