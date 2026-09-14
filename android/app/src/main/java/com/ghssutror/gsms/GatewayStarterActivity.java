package com.ghssutror.gsms;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.widget.Toast;

/**
 * Starts the local GSMS PC gateway while the app is visibly in the foreground,
 * then opens the normal SMS screen. This keeps the USB/Wi-Fi gateway alive
 * without requiring ADB or any third-party application.
 */
public class GatewayStarterActivity extends Activity {
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            Intent service = new Intent(this, SmsGatewayService.class);
            service.setAction(SmsGatewayService.ACTION_START);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(service);
            else startService(service);
            Toast.makeText(this, "GSMS PC gateway started. Check the notification for IP and token.", Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, "Gateway could not start: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
        startActivity(new Intent(this, MainActivity.class));
        finish();
    }
}
