// Minimal hook: just list modules to prove Frida works
var cocos = Process.findModuleByName("libcocos2dcpp.so");
if (cocos) {
    console.log("[OK] libcocos2dcpp.so base=" + cocos.base + " size=" + cocos.size);
} else {
    console.log("[FAIL] libcocos2dcpp.so not found");
    Process.enumerateModules().forEach(function(m) {
        if (m.name.indexOf("cocos") !== -1 || m.name.indexOf("khux") !== -1)
            console.log("  " + m.name + " @ " + m.base);
    });
}
