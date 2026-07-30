package com.ghssutror.gsms;

import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.telephony.SmsManager;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.*;

public class SmsGatewayService extends Service {
    public static final String ACTION_START = "com.ghssutror.gsms.START";
    public static final String ACTION_STOP = "com.ghssutror.gsms.STOP";
    private static final int NOTIFICATION_ID = 1001;
    private volatile boolean running = false;
    private ServerSocket server;
    private ExecutorService pool;

    @Override public void onCreate() {
        super.onCreate();
        createChannel();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) { stopGateway(); return START_NOT_STICKY; }
        startGateway();
        return START_STICKY;
    }

    private synchronized void startGateway() {
        if (running) return;
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            // Service can still run; notification visibility depends on user permission.
        }
        startForeground(NOTIFICATION_ID, notification("GSMS SMS gateway running on port " + GatewayConfig.PORT));
        running = true;
        pool = Executors.newCachedThreadPool();
        pool.execute(this::serverLoop);
    }

    private void serverLoop() {
        try {
            server = new ServerSocket(GatewayConfig.PORT, 20, InetAddress.getByName("0.0.0.0"));
            while (running) {
                Socket s = server.accept();
                pool.execute(() -> handle(s));
            }
        } catch (IOException ignored) {
        } finally { closeServer(); }
    }

    private void handle(Socket socket) {
        try (Socket s = socket) {
            s.setSoTimeout(10000);
            BufferedReader r = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
            String request = r.readLine();
            if (request == null) return;
            Map<String,String> headers = new HashMap<>();
            String line;
            while ((line = r.readLine()) != null && !line.isEmpty()) {
                int p = line.indexOf(':'); if (p > 0) headers.put(line.substring(0,p).trim().toLowerCase(Locale.US), line.substring(p+1).trim());
            }
            if (!"POST".equalsIgnoreCase(request.split(" ")[0])) { reply(s, 405, "Only POST is supported"); return; }
            if (!GatewayConfig.getToken(this).equals(headers.get("x-gsms-token"))) { reply(s, 401, "Invalid token"); return; }
            int len = Integer.parseInt(headers.getOrDefault("content-length", "0"));
            char[] body = new char[len]; int read=0; while(read<len){ int n=r.read(body,read,len-read); if(n<0) break; read+=n; }
            String json = new String(body,0,read);
            String phone = field(json,"phone"); String message = field(json,"message");
            if (phone.isEmpty() || message.isEmpty()) { reply(s,400,"phone and message are required"); return; }
            sendSmsSim1(phone,message);
            reply(s,200,"{\"ok\":true,\"status\":\"accepted\"}",true);
        } catch (Exception e) { try { reply(socket,500,"Server error: "+e.getMessage()); } catch(Exception ignored){} }
    }

    private void sendSmsSim1(String phone, String message) {
        if (checkSelfPermission("android.permission.SEND_SMS") != PackageManager.PERMISSION_GRANTED) throw new SecurityException("SEND_SMS permission not granted");
        SmsManager sms = getSim1SmsManager();
        ArrayList<String> parts = sms.divideMessage(message);
        if (parts.size() == 1) sms.sendTextMessage(phone, null, message, null, null);
        else sms.sendMultipartTextMessage(phone, null, parts, null, null);
    }

    private SmsManager getSim1SmsManager() {
        if (Build.VERSION.SDK_INT >= 22 && checkSelfPermission("android.permission.READ_PHONE_STATE") == PackageManager.PERMISSION_GRANTED) {
            SubscriptionManager sm = (SubscriptionManager)getSystemService(TELEPHONY_SUBSCRIPTION_SERVICE);
            List<SubscriptionInfo> list = sm.getActiveSubscriptionInfoList();
            if (list != null) for (SubscriptionInfo info : list) if (info.getSimSlotIndex() == 0) return SmsManager.getSmsManagerForSubscriptionId(info.getSubscriptionId());
        }
        return SmsManager.getDefault();
    }

    private String field(String json,String key) {
        Pattern p=Pattern.compile("\\\""+Pattern.quote(key)+"\\\"\\s*:\\s*\\\"((?:\\\\.|[^\\\"])*)\\\"");
        Matcher m=p.matcher(json); if(!m.find()) return "";
        return m.group(1).replace("\\\"","\"").replace("\\\\","\\");
    }

    private void reply(Socket s,int code,String body) throws IOException { reply(s,code,body,false); }
    private void reply(Socket s,int code,String body,boolean json) throws IOException {
        String ct=json?"application/json":"text/plain; charset=utf-8";
        String h="HTTP/1.1 "+code+" OK\r\nContent-Type: "+ct+"\r\nContent-Length: "+body.getBytes(StandardCharsets.UTF_8).length+"\r\nConnection: close\r\n\r\n";
        s.getOutputStream().write((h+body).getBytes(StandardCharsets.UTF_8)); s.getOutputStream().flush();
    }

    private Notification notification(String text){ return new Notification.Builder(this,"gsms").setSmallIcon(android.R.drawable.sym_action_email).setContentTitle("GSMS SMS v1.0").setContentText(text).setOngoing(true).build(); }
    private void createChannel(){ if(Build.VERSION.SDK_INT>=26){ NotificationManager nm=getSystemService(NotificationManager.class); nm.createNotificationChannel(new NotificationChannel("gsms","GSMS SMS Gateway",NotificationManager.IMPORTANCE_LOW)); } }
    private synchronized void stopGateway(){ running=false; closeServer(); if(pool!=null) pool.shutdownNow(); stopForeground(true); stopSelf(); }
    private void closeServer(){ try{ if(server!=null) server.close(); }catch(IOException ignored){} server=null; }
    @Override public void onDestroy(){ stopGateway(); super.onDestroy(); }
    @Override public android.os.IBinder onBind(Intent intent){ return null; }
}
