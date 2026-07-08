/**
 * 在浏览器 Console 中运行此脚本以提取 TAC RSA 公钥
 *
 * 使用方法:
 * 1. 打开 https://seat.lib.whu.edu.cn/seat/ 并登录
 * 2. F12 打开 DevTools → Console
 * 3. 粘贴以下代码并回车
 * 4. 复制输出的 RSA 公钥
 */

(function() {
    console.log('=== TAC RSA 公钥提取 ===');

    // 方法 1: 从 TAC.enc.rsaPublicKey 获取
    if (typeof TAC !== 'undefined' && TAC.enc && TAC.enc.rsaPublicKey) {
        console.log('[方法1] TAC.enc.rsaPublicKey:');
        console.log(TAC.enc.rsaPublicKey);
    } else {
        console.log('[方法1] TAC.enc.rsaPublicKey 未找到');
    }

    // 方法 2: 从 sessionStorage systemInfo 获取
    try {
        var sysInfo = JSON.parse(sessionStorage.getItem('systemInfo'));
        if (sysInfo) {
            console.log('[方法2] systemInfo keys:', Object.keys(sysInfo));
            console.log('[方法2] systemInfo.mackCaptcha keys:',
                sysInfo.mackCaptcha ? Object.keys(sysInfo.mackCaptcha) : 'N/A');
            console.log('[方法2] systemInfo JSON:');
            console.log(JSON.stringify(sysInfo, null, 2));
        }
    } catch(e) {
        console.log('[方法2] systemInfo 解析失败:', e.message);
    }

    // 方法 3: 搜索所有 sessionStorage
    console.log('[方法3] 所有 sessionStorage keys:');
    for (var i = 0; i < sessionStorage.length; i++) {
        var key = sessionStorage.key(i);
        var val = sessionStorage.getItem(key);
        console.log('  ' + key + ': ' + val.substring(0, 200));
    }

    // 方法 4: 查找 MIGf 开头的 Base64 (1024-bit RSA key)
    console.log('[方法4] 搜索页面中的 RSA 公钥...');
    var scripts = document.querySelectorAll('script');
    scripts.forEach(function(s) {
        if (s.src) {
            console.log('  检查:', s.src);
        }
    });

    console.log('=== 完成 ===');
    console.log('请将上面包含 "MIGf" 开头的长字符串复制给我');
})();
