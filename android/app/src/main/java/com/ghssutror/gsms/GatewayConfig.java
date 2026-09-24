package com.ghssutror.gsms;

import android.content.Context;
import java.net.Inet4Address;
import java.net.NetworkInterface;
import java.net.SocketException;
import java.util.Collections;
import java.util.Enumeration;
import java.util.Locale;
import java.util.UUID;

public final class GatewayConfig {
    public static final int PORT = 8765;
    private static final String PREFS = "gsms_prefs";
    private static final String TOKEN = "token";
    private GatewayConfig() {}

    public static void setToken(Context c, String token) {
        c.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(TOKEN, token == null ? "" : token.trim())
                .apply();
    }

    public static String getToken(Context c) {
        String t = c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(TOKEN, null);
        if (t == null || t.trim().isEmpty()) {
            t = "GSMS-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.US);
            c.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(TOKEN, t).apply();
        }
        return t;
    }

    /**
     * Returns an active non-loopback IPv4 address. This deliberately does not
     * depend only on Wi-Fi, because the PC/phone link may be USB tethering.
     */
    public static String getLocalIp(Context c) {
        try {
            Enumeration<NetworkInterface> interfaces = NetworkInterface.getNetworkInterfaces();
            if (interfaces == null) return "<phone-ip>";
            String fallback = "";
            for (NetworkInterface ni : Collections.list(interfaces)) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                String name = ni.getName() == null ? "" : ni.getName().toLowerCase(Locale.US);
                for (java.net.InetAddress address : Collections.list(ni.getInetAddresses())) {
                    if (!(address instanceof Inet4Address) || address.isLoopbackAddress()) continue;
                    String ip = address.getHostAddress();
                    if (ip == null || ip.startsWith("127.")) continue;
                    // Prefer USB/RNDIS-style private interfaces when available.
                    if (name.contains("rndis") || name.contains("usb") || name.contains("ether")) return ip;
                    if (fallback.isEmpty()) fallback = ip;
                }
            }
            return fallback.isEmpty() ? "<phone-ip>" : fallback;
        } catch (Exception e) {
            return "<phone-ip>";
        }
    }
}
