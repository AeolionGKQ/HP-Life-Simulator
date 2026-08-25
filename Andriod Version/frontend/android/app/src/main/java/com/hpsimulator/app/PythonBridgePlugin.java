package com.hpsimulator.app;

import android.util.Log;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "PythonBridge")
public class PythonBridgePlugin extends Plugin {
    private static final Object PYTHON_START_LOCK = new Object();
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
}
