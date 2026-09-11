package com.ghssutror.gsms;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.telephony.SmsManager;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final int SMS_PERMISSION_REQUEST = 100;
    private EditText recipients;
    private EditText message;
    private TextView status;
    private TextView counter;
    private Button send;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        recipients = findViewById(R.id.recipients);
        message = findViewById(R.id.message);
        status = findViewById(R.id.status);
        counter = findViewById(R.id.counter);
        send = findViewById(R.id.send);
        Button clear = findViewById(R.id.clear);

        requestSmsPermission();
        updateCounter();

        message.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { updateCounter(); }
            @Override public void afterTextChanged(Editable s) { }
        });

        send.setOnClickListener(v -> sendSmsBatch());
        clear.setOnClickListener(v -> {
            recipients.setText("");
            message.setText("");
            status.setText("Ready — SMS will be sent through SIM 1.");
        });
    }

    private void requestSmsPermission() {
        if (Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.SEND_SMS}, SMS_PERMISSION_REQUEST);
        }
    }

    private void updateCounter() {
        int length = message == null ? 0 : message.getText().length();
        counter.setText("Message length: " + length + " characters");
    }

    private void sendSmsBatch() {
        if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestSmsPermission();
            status.setText("SMS permission is required.");
            return;
        }

        String rawRecipients = recipients.getText().toString().trim();
        String text = message.getText().toString().trim();
        if (rawRecipients.isEmpty()) {
            recipients.setError("Enter at least one mobile number.");
            return;
        }
        if (text.isEmpty()) {
            message.setError("Enter the SMS message.");
            return;
        }

        List<String> numbers = parseRecipients(rawRecipients);
        if (numbers.isEmpty()) {
            status.setText("No valid mobile numbers found.");
            return;
        }

        SmsManager smsManager = getSim1SmsManager();
        if (smsManager == null) {
            status.setText("SIM 1 was not detected. Please check the SIM card.");
            Toast.makeText(this, "SIM 1 not available", Toast.LENGTH_LONG).show();
            return;
        }

        send.setEnabled(false);
        int sent = 0;
        for (String number : numbers) {
            try {
                ArrayList<String> parts = smsManager.divideMessage(text);
                if (parts.size() == 1) {
                    smsManager.sendTextMessage(number, null, text, null, null);
                } else {
                    ArrayList<android.app.PendingIntent> sentIntents = new ArrayList<>();
                    for (int i = 0; i < parts.size(); i++) sentIntents.add(null);
                    smsManager.sendMultipartTextMessage(number, null, parts, sentIntents, null);
                }
                sent++;
            } catch (Exception e) {
                android.util.Log.e("GSMS", "SMS failed for " + number, e);
            }
        }

        send.setEnabled(true);
        status.setText("SMS request sent to " + sent + " recipient(s) through SIM 1.");
        Toast.makeText(this, "Sent: " + sent + " recipient(s)", Toast.LENGTH_LONG).show();
    }

    private List<String> parseRecipients(String raw) {
        String[] items = raw.split("[\\s,;]+|");
        ArrayList<String> result = new ArrayList<>();
        for (String item : items) {
            String n = item.trim();
            if (!n.isEmpty()) result.add(n);
        }
        return result;
    }

    private SmsManager getSim1SmsManager() {
        try {
            SubscriptionManager sm = getSystemService(SubscriptionManager.class);
            if (sm == null) return null;
            List<SubscriptionInfo> list = sm.getActiveSubscriptionInfoList();
            if (list == null) return null;
            for (SubscriptionInfo info : list) {
                if (info.getSimSlotIndex() == 0) {
                    return SmsManager.getSmsManagerForSubscriptionId(info.getSubscriptionId());
                }
            }
            return null;
        } catch (SecurityException e) {
            return null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SMS_PERMISSION_REQUEST) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                status.setText("Ready — SMS will be sent through SIM 1.");
            } else {
                status.setText("SMS permission denied. Allow SMS permission in Settings.");
            }
        }
    }
}
