package com.ghssutror.gsms;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.widget.Button;
import android.widget.TextView;

public class MainActivity extends android.app.Activity {
    private TextView status;
    private TextView address;
    private TextView tokenView;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        status = findViewById(R.id.status);
        address = findViewById(R.id.address);
        tokenView = findViewById(R.id.token);
        Button start = findViewById(R.id.start);
        Button stop = findViewById(R.id.stop);

        requestNeededPermissions();
        refreshInfo();
        start.setOnClickListener(v -> startGateway());
        stop.setOnClickListener(v -> stopGateway());
    }

    private void requestNeededPermissions() {
        if (Build.VERSION.SDK_INT >= 23) {
            if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED ||
                checkSelfPermission(Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.SEND_SMS, Manifest.permission.READ_PHONE_STATE}, 50);
            }
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 51);
            }
        }
    }

    private void startGateway() {
        Intent i = new Intent(this, SmsGatewayService.class).setAction(SmsGatewayService.ACTION_START);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
        refreshInfo();
    }

    private void stopGateway() {
        Intent i = new Intent(this, SmsGatewayService.class).setAction(SmsGatewayService.ACTION_STOP);
        startService(i);
        status.setText("Server stopped");
    }

    private void refreshInfo() {
        tokenView.setText("Pairing token: " + GatewayConfig.getToken(this));
        address.setText("PC gateway address: http://" + GatewayConfig.getLocalIp(this) + ":8765");
    }
}
