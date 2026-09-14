package com.ghssutror.gsms;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.Toast;

/**
 * Starts the local GSMS PC gateway while the app is visibly in the foreground,
 * then opens the normal SMS screen. No ADB or third-party application is used.
 */
public class GatewayStarterActivity extends Activity {
    private static final int NOTIFICATION_REQUEST = 700;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            Intent service = new Intent(this, SmsGatewayService.class);
            service.setAction(SmsGatewayService.ACTION_START);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
            else startService(service);

            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_REQUEST);
            }

            String ip = GatewayConfig.getLocalIp(this);
            String token = GatewayConfig.getToken(this);
            Toast.makeText(this,
                    "GSMS gateway started\nPC URL: http://" + ip + ":" + GatewayConfig.PORT + "\nToken: " + token,
                    Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, "Gateway could not start: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }
}
