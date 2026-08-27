package com.hpsimulator.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import androidx.activity.result.ActivityResult;

@CapacitorPlugin(name = "PythonBridge")
public class PythonBridgePlugin extends Plugin {
    private static final Object PYTHON_START_LOCK = new Object();
    private static final int FILE_PICKER_REQUEST = 4101;
    private static final int FILE_SAVER_REQUEST = 4102;
    private final ExecutorService pythonExecutor = Executors.newCachedThreadPool();

    private void ensurePythonStarted() {
        synchronized (PYTHON_START_LOCK) {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(getContext()));
            }
        }
    }

    @PluginMethod
    public void probe(PluginCall call) {
        pythonExecutor.execute(() -> probeOnBackground(call));
    }

    private void probeOnBackground(PluginCall call) {
        try {
            ensurePythonStarted();

            Python python = Python.getInstance();
            PyObject module = python.getModule("mobile_validation");
            PyObject message = module.callAttr(
                "probe",
                getContext().getFilesDir().getAbsolutePath()
            );

            JSObject result = new JSObject();
            result.put("status", "ok");
            result.put("message", message.toString());
            result.put("pythonVersion", python.getModule("sys").get("version").toString());
            result.put("filesDir", getContext().getFilesDir().getAbsolutePath());
            call.resolve(result);
        } catch (Exception exception) {
            call.reject("无法启动内嵌 Python", exception);
        }
    }

    @PluginMethod
    public void request(PluginCall call) {
        pythonExecutor.execute(() -> requestOnBackground(call));
    }

    private void requestOnBackground(PluginCall call) {
        try {
            ensurePythonStarted();

            String path = call.getString("path");
            String method = call.getString("method", "GET");
            String body = call.getString("body", "");
            if (path == null || path.isEmpty()) {
                call.reject("本地请求缺少 path");
                return;
            }

            PyObject mobileApi = Python.getInstance().getModule("mobile_api");
            PyObject payload = mobileApi.callAttr(
                "request",
                path,
                method,
                body,
                getContext().getFilesDir().getAbsolutePath()
            );

            JSObject result = new JSObject();
            result.put("payload", payload.toString());
            call.resolve(result);
        } catch (Exception exception) {
            Log.e("PythonBridge", "Python request failed", exception);
            String detail = exception.getMessage();
            call.reject(
                detail == null || detail.isEmpty()
                    ? "本地 Python 请求失败"
                    : "本地 Python 请求失败：" + detail,
                exception
            );
        }
    }

    @PluginMethod
    public void pickFile(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(call, intent, "handlePickFile");
    }

    @ActivityCallback
    private void handlePickFile(PluginCall call, ActivityResult result) {
        if (result == null || result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
            call.reject("已取消读取存档");
            return;
        }
        Uri uri = result.getData().getData();
        if (uri == null) {
            call.reject("未选择存档文件");
            return;
        }
        try (InputStream input = getContext().getContentResolver().openInputStream(uri);
             BufferedReader reader = new BufferedReader(
                 new InputStreamReader(input, StandardCharsets.UTF_8))) {
            StringBuilder content = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                content.append(line).append('\n');
            }
            JSObject response = new JSObject();
            response.put("content", content.toString());
            response.put("filename", uri.getLastPathSegment() == null ? "存档.json" : uri.getLastPathSegment());
            response.put("uri", uri.toString());
            call.resolve(response);
        } catch (Exception exception) {
            call.reject("无法读取存档文件", exception);
        }
    }

    @PluginMethod
    public void prepareSaveFile(PluginCall call) {
        String content = call.getString("content");
        if (content == null) {
            call.reject("导出存档内容为空");
            return;
        }
        pythonExecutor.execute(() -> prepareSaveFileOnBackground(call, content));
    }

    private void prepareSaveFileOnBackground(PluginCall call, String content) {
        File stagedFile = null;
        try {
            File exportDirectory = new File(getContext().getCacheDir(), "exports");
            if (!exportDirectory.isDirectory() && !exportDirectory.mkdirs()) {
                call.reject("无法创建存档临时目录");
                return;
            }
            String token = java.util.UUID.randomUUID().toString() + ".json";
            stagedFile = new File(exportDirectory, token);
            try (BufferedWriter writer = new BufferedWriter(
                new OutputStreamWriter(new FileOutputStream(stagedFile), StandardCharsets.UTF_8))) {
                writer.write(content);
            }

            JSObject response = new JSObject();
            response.put("token", token);
            call.resolve(response);
        } catch (Exception exception) {
            if (stagedFile != null) {
                stagedFile.delete();
            }
            call.reject("无法准备导出存档", exception);
        }
    }

    @PluginMethod
    public void saveFile(PluginCall call) {
        String filename = call.getString("filename", "霍格沃兹存档.hp-save.json");
        String token = call.getString("token");
        if (token == null || token.isEmpty()) {
            call.reject("导出存档临时文件无效");
            return;
        }
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        intent.putExtra(Intent.EXTRA_TITLE, filename);
        startActivityForResult(call, intent, "handleSaveFile");
    }

    private File resolveStagedExport(String token) throws Exception {
        File exportDirectory = new File(getContext().getCacheDir(), "exports").getCanonicalFile();
        File stagedFile = new File(exportDirectory, token).getCanonicalFile();
        String directoryPath = exportDirectory.getPath() + File.separator;
        if (!stagedFile.getPath().startsWith(directoryPath)) {
            throw new IllegalArgumentException("导出存档临时文件无效");
        }
        return stagedFile;
    }

    @ActivityCallback
    private void handleSaveFile(PluginCall call, ActivityResult result) {
        String token = call.getString("token");
        File stagedFile = null;
        try {
            if (token != null && !token.isEmpty()) {
                stagedFile = resolveStagedExport(token);
            }
        } catch (Exception exception) {
            call.reject("导出存档临时文件无效", exception);
            return;
        }
        if (result == null || result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
            deleteStagedExport(stagedFile);
            call.reject("已取消导出存档");
            return;
        }
        Uri uri = result.getData().getData();
        if (uri == null || stagedFile == null || !stagedFile.isFile()) {
            deleteStagedExport(stagedFile);
            call.reject("未选择存档保存位置");
            return;
        }
        try (InputStream input = new BufferedInputStream(new FileInputStream(stagedFile));
             OutputStream output = getContext().getContentResolver().openOutputStream(uri)) {
            if (output == null) {
                call.reject("无法打开存档保存位置");
                return;
            }
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            output.flush();
            JSObject response = new JSObject();
            response.put("saved", true);
            response.put("uri", uri.toString());
            call.resolve(response);
        } catch (Exception exception) {
            call.reject("无法写入存档文件", exception);
        } finally {
            deleteStagedExport(stagedFile);
        }
    }

    private void deleteStagedExport(File stagedFile) {
        if (stagedFile != null && stagedFile.exists() && !stagedFile.delete()) {
            Log.w("PythonBridge", "Unable to delete staged export: " + stagedFile.getAbsolutePath());
        }
    }
}
