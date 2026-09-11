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
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends Activity {
    private static final int SMS_PERMISSION_REQUEST = 100;
    private static final String[] REQUIRED_PERMISSIONS = new String[]{
            Manifest.permission.SEND_SMS,
            Manifest.permission.READ_PHONE_STATE
    };

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

        requestRequiredPermissions();
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

    private void requestRequiredPermissions() {
        if (Build.VERSION.SDK_INT >= 23) {
            ArrayList<String> missing = new ArrayList<>();
            for (String permission : REQUIRED_PERMISSIONS) {
                if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
                    missing.add(permission);
                }
            }
            if (!missing.isEmpty()) {
                requestPermissions(missing.toArray(new String[0]), SMS_PERMISSION_REQUEST);
            }
        }
    }

    private boolean hasRequiredPermissions() {
        if (Build.VERSION.SDK_INT < 23) return true;
        return checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
    }

    private void updateCounter() {
        int length = message == null ? 0 : message.getText().length();
        counter.setText("Message length: " + length + " characters");
    }

    private void sendSmsBatch() {
        if (!hasRequiredPermissions()) {
            requestRequiredPermissions();
            status.setText("Allow SMS and Phone permissions so GSMS can detect SIM 1.");
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
            status.setText("SIM 1 was not detected. Please check SIM 1 and Phone permission.");
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
                    smsManager.sendMultipartTextMessage(number, null, parts, null, null);
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
        String[] items = raw.split("[\\s,;]+");
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
            if (list == null || list.isEmpty()) return null;

            for (SubscriptionInfo info : list) {
                if (info != null && info.getSimSlotIndex() == 0) {
                    return SmsManager.getSmsManagerForSubscriptionId(info.getSubscriptionId());
                }
            }
            return null;
        } catch (SecurityException e) {
            android.util.Log.e("GSMS", "Unable to read active SIM subscriptions", e);
            return null;
        } catch (Exception e) {
            android.util.Log.e("GSMS", "SIM detection failed", e);
            return null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SMS_PERMISSION_REQUEST) {
            if (hasRequiredPermissions()) {
                status.setText("SIM permissions granted. Ready — SMS will be sent through SIM 1.");
            } else {
                status.setText("Please allow SMS and Phone permissions in Settings.");
            }
        }
    }
}
