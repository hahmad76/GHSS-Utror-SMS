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
    private static final String PREFS = "gsms_prefs";
    private static final String KEY_RUNNING = "gateway_running";
    private static final String KEY_ERROR = "gateway_error";
    private volatile boolean running = false;
    private ServerSocket server;
    private ExecutorService pool;

    @Override public void onCreate() { super.onCreate(); createChannel(); }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) { stopGateway(); return START_NOT_STICKY; }
        startGateway();
        return START_STICKY;
    }

    private synchronized void startGateway() {
        if (running) return;
        clearState();
        String ip = GatewayConfig.getLocalIp(this);
        String token = GatewayConfig.getToken(this);
        startForeground(NOTIFICATION_ID, notification("PC gateway: " + ip + ":" + GatewayConfig.PORT + " | Token: " + token));
        running = true;
        pool = Executors.newCachedThreadPool();
        pool.execute(this::serverLoop);
    }

    private void serverLoop() {
        try {
            ServerSocket ss = new ServerSocket();
            ss.setReuseAddress(true);
            ss.bind(new InetSocketAddress(InetAddress.getByName("0.0.0.0"), GatewayConfig.PORT), 20);
            server = ss;
            setState(true, "");
            updateNotification("PC gateway READY: " + GatewayConfig.getLocalIp(this) + ":" + GatewayConfig.PORT + " | Token: " + GatewayConfig.getToken(this));
            while (running) {
                Socket s = server.accept();
                pool.execute(() -> handle(s));
            }
        } catch (IOException e) {
            if (running) setState(false, "Could not open port " + GatewayConfig.PORT + ": " + e.getMessage());
        } catch (Exception e) {
            if (running) setState(false, "Gateway error: " + e.getMessage());
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
                int p = line.indexOf(':');
                if (p > 0) headers.put(line.substring(0,p).trim().toLowerCase(Locale.US), line.substring(p+1).trim());
            }
            String[] requestParts = request.split(" ");
            if (requestParts.length < 2) { reply(s,400,"Bad request"); return; }
            String method = requestParts[0];
            String path = requestParts[1];

            if ("GET".equalsIgnoreCase(method)) {
                if ("/".equals(path) || "/health".equals(path)) {
                    String body = "{\"ok\":true,\"service\":\"GSMS SMS Gateway\",\"port\":" + GatewayConfig.PORT + ",\"ip\":\"" + GatewayConfig.getLocalIp(this) + "\"}";
                    reply(s,200,body,true);
                } else reply(s,404,"Not found");
                return;
            }

            if (!"POST".equalsIgnoreCase(method)) { reply(s,405,"Only POST and GET are supported"); return; }
            if (!GatewayConfig.getToken(this).equals(headers.get("x-gsms-token"))) { reply(s,401,"Invalid token"); return; }
            int len = Integer.parseInt(headers.getOrDefault("content-length", "0"));
            char[] bodyChars = new char[len];
            int read=0;
            while(read<len){ int n=r.read(bodyChars,read,len-read); if(n<0) break; read+=n; }
            String json = new String(bodyChars,0,read);
            String phone = field(json,"phone");
            String message = field(json,"message");
            if (phone.isEmpty() || message.isEmpty()) { reply(s,400,"phone and message are required"); return; }
            sendSmsSim1(phone,message);
            reply(s,200,"{\"ok\":true,\"status\":\"accepted\"}",true);
        } catch (Exception e) {
            try { reply(socket,500,"Server error: "+e.getMessage()); } catch(Exception ignored){}
        }
    }

    private void sendSmsSim1(String phone, String message) {
        if (checkSelfPermission("android.permission.SEND_SMS") != PackageManager.PERMISSION_GRANTED)
            throw new SecurityException("SEND_SMS permission not granted");
        SmsManager sms = getSim1SmsManager();
        ArrayList<String> parts = sms.divideMessage(message);
        if (parts.size() == 1) sms.sendTextMessage(phone, null, message, null, null);
        else sms.sendMultipartTextMessage(phone, null, parts, null, null);
    }

    private SmsManager getSim1SmsManager() {
        if (Build.VERSION.SDK_INT >= 22 && checkSelfPermission("android.permission.READ_PHONE_STATE") == PackageManager.PERMISSION_GRANTED) {
            SubscriptionManager sm = (SubscriptionManager)getSystemService(TELEPHONY_SUBSCRIPTION_SERVICE);
            List<SubscriptionInfo> list = sm.getActiveSubscriptionInfoList();
            if (list != null) for (SubscriptionInfo info : list)
                if (info.getSimSlotIndex() == 0)
                    return SmsManager.getSmsManagerForSubscriptionId(info.getSubscriptionId());
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
        String status = code == 200 ? "OK" : (code == 400 ? "Bad Request" : code == 401 ? "Unauthorized" : code == 404 ? "Not Found" : code == 405 ? "Method Not Allowed" : "Error");
        String h="HTTP/1.1 "+code+" "+status+"\r\nContent-Type: "+ct+"\r\nContent-Length: "+body.getBytes(StandardCharsets.UTF_8).length+"\r\nConnection: close\r\n\r\n";
        s.getOutputStream().write((h+body).getBytes(StandardCharsets.UTF_8));
        s.getOutputStream().flush();
    }

    private Notification notification(String text){ return new Notification.Builder(this,"gsms").setSmallIcon(android.R.drawable.sym_action_email).setContentTitle("GSMS SMS v1.0").setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text)).setOngoing(true).build(); }
    private void updateNotification(String text){ ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(NOTIFICATION_ID, notification(text)); }
    private void createChannel(){ if(Build.VERSION.SDK_INT>=26){ NotificationManager nm=getSystemService(NotificationManager.class); nm.createNotificationChannel(new NotificationChannel("gsms","GSMS SMS Gateway",NotificationManager.IMPORTANCE_LOW)); } }
    private void setState(boolean ok, String error){ getSharedPreferences(PREFS,MODE_PRIVATE).edit().putBoolean(KEY_RUNNING,ok).putString(KEY_ERROR,error==null?"":error).apply(); }
    private void clearState(){ setState(false,""); }
    private synchronized void stopGateway(){ running=false; setState(false,""); closeServer(); if(pool!=null) pool.shutdownNow(); stopForeground(true); stopSelf(); }
    private void closeServer(){ try{ if(server!=null) server.close(); }catch(IOException ignored){} server=null; }
    @Override public void onDestroy(){ stopGateway(); super.onDestroy(); }
    @Override public android.os.IBinder onBind(Intent intent){ return null; }
}
