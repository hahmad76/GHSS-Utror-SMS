package com.ghssutror.gsms;

import android.content.Context;
import android.net.wifi.WifiManager;
import android.text.format.Formatter;
import java.util.UUID;

public final class GatewayConfig {
    public static final int PORT = 8765;
    private static final String PREFS = "gsms_prefs";
    private static final String TOKEN = "token";
    private GatewayConfig() {}

    public static String getToken(Context c) {
        String t = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(TOKEN, null);
        if (t == null) {
            t = "GSMS-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(TOKEN, t).apply();
        }
        return t;
    }

    public static String getLocalIp(Context c) {
        try {
            WifiManager wm = (WifiManager)c.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            return Formatter.formatIpAddress(wm.getConnectionInfo().getIpAddress());
        } catch (Exception e) { return "<phone-ip>"; }
    }
}
