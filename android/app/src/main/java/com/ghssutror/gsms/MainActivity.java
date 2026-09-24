package com.ghssutror.gsms;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.telephony.SmsManager;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public class MainActivity extends Activity {
    private static final int SMS_PERMISSION_REQUEST = 100;
    private static final int CSV_PICKER_REQUEST = 200;
    private static final String PREFS = "gsms_contacts";
    private static final String KEY_CONTACTS = "contacts_json";
    private static final String[] REQUIRED_PERMISSIONS = new String[]{
            Manifest.permission.SEND_SMS,
            Manifest.permission.READ_PHONE_STATE
    };

    private final ArrayList<Contact> contacts = new ArrayList<>();
    private EditText manualRecipients;
    private EditText message;
    private TextView status;
    private TextView counter;
    private TextView databaseInfo;
    private TextView recipientCount;
    private Spinner audienceSpinner;
    private Spinner filterSpinner;
    private Button send;

    private final String[] audiences = new String[]{
            "Entire School", "All Students", "Class", "Section",
            "Teaching Staff", "Non-Teaching Staff", "Manual Numbers"
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        status = findViewById(R.id.status);
        counter = findViewById(R.id.counter);
        databaseInfo = findViewById(R.id.databaseInfo);
        recipientCount = findViewById(R.id.recipientCount);
        audienceSpinner = findViewById(R.id.audienceSpinner);
        filterSpinner = findViewById(R.id.filterSpinner);
        manualRecipients = findViewById(R.id.manualRecipients);
        message = findViewById(R.id.message);
        send = findViewById(R.id.send);
        Button importCsv = findViewById(R.id.importCsv);
        Button clear = findViewById(R.id.clear);

        loadContacts();
        requestRequiredPermissions();

        audienceSpinner.setAdapter(new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, audiences));
        audienceSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                updateFilterOptions();
            }
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) { }
        });

        importCsv.setOnClickListener(v -> openCsvPicker());
        send.setOnClickListener(v -> sendSmsBatch());
        clear.setOnClickListener(v -> {
            message.setText("");
            status.setText("Ready — select an audience and send through SIM 1.");
        });
        message.addTextChangedListener(new android.text.TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { updateCounter(); }
            @Override public void afterTextChanged(android.text.Editable s) { }
        });

        updateCounter();
        updateDatabaseInfo();
        updateFilterOptions();
    }

    private void showGatewaySettings() {
        final EditText tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokenInput.setHint("Enter gateway token");
        tokenInput.setText(GatewayConfig.getToken(this));
        tokenInput.setSelection(tokenInput.length());

        String ip = GatewayConfig.getLocalIp(this);
        String url = "http://" + ip + ":" + GatewayConfig.PORT;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (16 * getResources().getDisplayMetrics().density);
        box.setPadding(pad, 0, pad, 0);

        TextView info = new TextView(this);
        info.setText("Gateway URL:\n" + url + "\n\nThe Windows GSMS software must use this URL and the same token.\n\nToken:");
        info.setTextSize(15);
        box.addView(info);
        box.addView(tokenInput);

        new AlertDialog.Builder(this)
                .setTitle("Android Gateway Settings")
                .setView(box)
                .setPositiveButton("SAVE TOKEN", (dialog, which) -> {
                    String token = tokenInput.getText().toString().trim();
                    if (token.isEmpty()) {
                        Toast.makeText(this, "Gateway token cannot be empty.", Toast.LENGTH_LONG).show();
                        return;
                    }
                    GatewayConfig.setToken(this, token);
                    status.setText("Gateway token saved. PC Gateway URL: " + url);
                    Toast.makeText(this, "Gateway token saved successfully.", Toast.LENGTH_LONG).show();
                })
                .setNeutralButton("GENERATE NEW", (dialog, which) -> {
                    String token = "GSMS-" + java.util.UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase(Locale.US);
                    GatewayConfig.setToken(this, token);
                    status.setText("New gateway token generated. Open Gateway Settings to view it.");
                    Toast.makeText(this, "New gateway token generated.", Toast.LENGTH_LONG).show();
                })
                .setNegativeButton("CANCEL", null)
                .show();
    }

    private void requestRequiredPermissions() {
        if (Build.VERSION.SDK_INT >= 23) {
            ArrayList<String> missing = new ArrayList<>();
            for (String permission : REQUIRED_PERMISSIONS) {
                if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) missing.add(permission);
            }
            if (!missing.isEmpty()) requestPermissions(missing.toArray(new String[0]), SMS_PERMISSION_REQUEST);
        }
    }

    private boolean hasRequiredPermissions() {
        if (Build.VERSION.SDK_INT < 23) return true;
        return checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
    }

    private void openCsvPicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/*");
        startActivityForResult(intent, CSV_PICKER_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == CSV_PICKER_REQUEST && resultCode == RESULT_OK && data != null && data.getData() != null) {
            importCsv(data.getData());
        }
    }

    private void importCsv(Uri uri) {
        ArrayList<Contact> imported = new ArrayList<>();
        try (InputStream in = getContentResolver().openInputStream(uri);
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            if (reader == null) throw new Exception("Unable to open CSV file");
            String headerLine = reader.readLine();
            if (headerLine == null) throw new Exception("CSV file is empty");
            List<String> headers = parseCsvLine(removeBom(headerLine));
            int mobile = findColumn(headers, "mobile", "mobile number", "phone", "phone number", "contact", "contact number", "cell", "cell number");
            int name = findColumn(headers, "student name", "name", "student", "staff name", "teacher name");
            int father = findColumn(headers, "father", "father name", "guardian", "guardian name", "parent", "parent name");
            int clazz = findColumn(headers, "class", "grade", "standard");
            int section = findColumn(headers, "section", "sec");
            int role = findColumn(headers, "category", "type", "role", "group", "staff type");
            if (mobile < 0) throw new Exception("Mobile Number column was not found in the CSV.");

            String line;
            while ((line = reader.readLine()) != null) {
                if (line.trim().isEmpty()) continue;
                List<String> row = parseCsvLine(line);
                String phone = value(row, mobile);
                if (phone.isEmpty()) continue;
                Contact c = new Contact(value(row, name), value(row, father), value(row, clazz), value(row, section), phone, value(row, role));
                imported.add(c);
            }
        } catch (Exception e) {
            status.setText("CSV import failed: " + e.getMessage());
            Toast.makeText(this, "CSV import failed", Toast.LENGTH_LONG).show();
            return;
        }

        contacts.clear();
        contacts.addAll(imported);
        saveContacts();
        updateDatabaseInfo();
        updateFilterOptions();
        status.setText("CSV imported successfully. Select a group to send bulk SMS.");
        Toast.makeText(this, "Imported " + contacts.size() + " contact(s)", Toast.LENGTH_LONG).show();
    }

    private String removeBom(String s) {
        return s != null && s.startsWith("\uFEFF") ? s.substring(1) : s;
    }

    private int findColumn(List<String> headers, String... names) {
        for (int i = 0; i < headers.size(); i++) {
            String h = normalize(headers.get(i));
            for (String n : names) if (h.equals(normalize(n))) return i;
        }
        return -1;
    }

    private String normalize(String s) {
        return s == null ? "" : s.toLowerCase(Locale.US).replaceAll("[^a-z0-9]", "");
    }

    private String value(List<String> row, int index) {
        return index >= 0 && index < row.size() ? row.get(index).trim() : "";
    }

    private List<String> parseCsvLine(String line) {
        ArrayList<String> fields = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"'); i++;
                } else quoted = !quoted;
            } else if (ch == ',' && !quoted) {
                fields.add(current.toString()); current.setLength(0);
            } else current.append(ch);
        }
        fields.add(current.toString());
        return fields;
    }

    private void updateFilterOptions() {
        String audience = (String) audienceSpinner.getSelectedItem();
        if (audience == null) audience = audiences[0];
        manualRecipients.setVisibility(audience.equals("Manual Numbers") ? View.VISIBLE : View.GONE);

        ArrayList<String> options = new ArrayList<>();
        if (audience.equals("Class")) {
            Set<String> classes = new LinkedHashSet<>();
            for (Contact c : contacts) if (!c.clazz.isEmpty()) classes.add(c.clazz);
            options.addAll(classes);
            if (options.isEmpty()) options.add("No classes imported");
        } else if (audience.equals("Section")) {
            Set<String> sections = new LinkedHashSet<>();
            for (Contact c : contacts) {
                if (!c.section.isEmpty()) {
                    sections.add(c.clazz.isEmpty() ? c.section : c.clazz + " - " + c.section);
                }
            }
            options.addAll(sections);
            if (options.isEmpty()) options.add("No sections imported");
        } else {
            options.add("No additional filter");
        }
        filterSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, options));
        filterSpinner.setVisibility((audience.equals("Class") || audience.equals("Section")) ? View.VISIBLE : View.GONE);
        updateRecipientCount();
    }

    private ArrayList<String> getSelectedNumbers() {
        String audience = (String) audienceSpinner.getSelectedItem();
        ArrayList<String> result = new ArrayList<>();
        if (audience == null) audience = "Entire School";

        if (audience.equals("Manual Numbers")) {
            for (String item : manualRecipients.getText().toString().trim().split("[\\s,;]+")) {
                if (!item.trim().isEmpty()) result.add(item.trim());
            }
            return uniqueNumbers(result);
        }

        String filter = filterSpinner.getSelectedItem() == null ? "" : filterSpinner.getSelectedItem().toString();
        for (Contact c : contacts) {
            boolean include;
            switch (audience) {
                case "All Students": include = isStudent(c); break;
                case "Teaching Staff": include = isTeachingStaff(c); break;
                case "Non-Teaching Staff": include = isNonTeachingStaff(c); break;
                case "Class": include = !filter.startsWith("No ") && c.clazz.equalsIgnoreCase(filter); break;
                case "Section": include = !filter.startsWith("No ") && (c.clazz + " - " + c.section).equalsIgnoreCase(filter); break;
                default: include = true;
            }
            if (include && !c.mobile.isEmpty()) result.add(c.mobile);
        }
        return uniqueNumbers(result);
    }

    private boolean isStudent(Contact c) {
        String r = c.role.toLowerCase(Locale.US);
        return !r.contains("staff") && !r.contains("teacher") && !r.contains("employee") && !c.clazz.isEmpty();
    }

    private boolean isTeachingStaff(Contact c) {
        String r = c.role.toLowerCase(Locale.US);
        return r.contains("teacher") || r.contains("teaching") || r.contains("principal") || r.contains("headmaster") || r.contains("head teacher");
    }

    private boolean isNonTeachingStaff(Contact c) {
        String r = c.role.toLowerCase(Locale.US);
        return r.contains("non-teaching") || r.contains("non teaching") || r.contains("clerical") || r.contains("class iv") || r.contains("support staff") || r.contains("peon");
    }

    private ArrayList<String> uniqueNumbers(List<String> input) {
        return new ArrayList<>(new LinkedHashSet<>(input));
    }

    private void updateRecipientCount() {
        if (recipientCount != null) recipientCount.setText("Recipients: " + getSelectedNumbers().size());
    }

    private void updateCounter() {
        int length = message == null ? 0 : message.getText().length();
        if (counter != null) counter.setText("Message length: " + length + " characters");
    }

    private void sendSmsBatch() {
        if (!hasRequiredPermissions()) {
            requestRequiredPermissions();
            status.setText("Allow SMS and Phone permissions so GSMS can use SIM 1.");
            return;
        }
        String text = message.getText().toString().trim();
        if (text.isEmpty()) { message.setError("Enter the SMS message."); return; }

        final ArrayList<String> numbers = getSelectedNumbers();
        if (numbers.isEmpty()) {
            status.setText("No recipients found. Import a CSV and select an audience.");
            return;
        }

        final SmsManager smsManager = getSim1SmsManager();
        if (smsManager == null) {
            status.setText("SIM 1 was not detected. Please check SIM 1 and Phone permission.");
            Toast.makeText(this, "SIM 1 not available", Toast.LENGTH_LONG).show();
            return;
        }

        send.setEnabled(false);
        status.setText("Starting bulk SMS: 0 / " + numbers.size());
        final String finalText = text;
        new Thread(() -> {
            int sent = 0;
            int failed = 0;
            for (String number : numbers) {
                try {
                    ArrayList<String> parts = smsManager.divideMessage(finalText);
                    if (parts.size() == 1) smsManager.sendTextMessage(number, null, finalText, null, null);
                    else smsManager.sendMultipartTextMessage(number, null, parts, null, null);
                    sent++;
                } catch (Exception e) {
                    failed++;
                    android.util.Log.e("GSMS", "SMS failed for " + number, e);
                }
                int done = sent + failed;
                final int fSent = sent, fFailed = failed, fDone = done;
                runOnUiThread(() -> status.setText("Sending bulk SMS: " + fDone + " / " + numbers.size() + "  |  Sent: " + fSent + "  Failed: " + fFailed));
                try { Thread.sleep(300); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); break; }
            }
            runOnUiThread(() -> {
                send.setEnabled(true);
                status.setText("Bulk SMS completed. Check the phone's SMS status for final delivery results.");
                Toast.makeText(this, "Bulk SMS request completed for " + numbers.size() + " recipient(s)", Toast.LENGTH_LONG).show();
            });
        }).start();
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
        } catch (SecurityException e) {
            android.util.Log.e("GSMS", "Unable to read active SIM subscriptions", e);
        } catch (Exception e) {
            android.util.Log.e("GSMS", "SIM detection failed", e);
        }
        return null;
    }

    private void saveContacts() {
        try {
            JSONArray array = new JSONArray();
            for (Contact c : contacts) {
                JSONObject o = new JSONObject();
                o.put("name", c.name); o.put("father", c.father); o.put("class", c.clazz);
                o.put("section", c.section); o.put("mobile", c.mobile); o.put("role", c.role);
                array.put(o);
            }
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_CONTACTS, array.toString()).apply();
        } catch (Exception e) { android.util.Log.e("GSMS", "Unable to save contacts", e); }
    }

    private void loadContacts() {
        try {
            String raw = getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_CONTACTS, "");
            if (raw.isEmpty()) return;
            JSONArray array = new JSONArray(raw);
            for (int i = 0; i < array.length(); i++) {
                JSONObject o = array.getJSONObject(i);
                contacts.add(new Contact(o.optString("name"), o.optString("father"), o.optString("class"),
                        o.optString("section"), o.optString("mobile"), o.optString("role")));
            }
        } catch (Exception e) { android.util.Log.e("GSMS", "Unable to load contacts", e); }
    }

    private void updateDatabaseInfo() {
        databaseInfo.setText(contacts.isEmpty() ? "No CSV imported yet." : "Local database: " + contacts.size() + " contact(s) loaded from CSV.");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SMS_PERMISSION_REQUEST) {
            status.setText(hasRequiredPermissions()
                    ? "SIM permissions granted. Select an audience and send through SIM 1."
                    : "Please allow SMS and Phone permissions in Settings.");
        }
    }

    private static class Contact {
        final String name, father, clazz, section, mobile, role;
        Contact(String name, String father, String clazz, String section, String mobile, String role) {
            this.name = name; this.father = father; this.clazz = clazz; this.section = section; this.mobile = mobile; this.role = role;
        }
    }
}
