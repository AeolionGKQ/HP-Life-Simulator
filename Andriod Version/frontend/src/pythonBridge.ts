import { Capacitor, registerPlugin } from "@capacitor/core";

interface PythonProbeResult {
  status: string;
  message: string;
  pythonVersion: string;
  filesDir: string;
}

interface PythonBridgePlugin {
  probe(): Promise<PythonProbeResult>;
  request(payload: {
    path: string;
    method: string;
    body: string;
  }): Promise<{ payload: string }>;
  prepareSaveFile(payload: {
    content: string;
  }): Promise<{ token: string }>;
  saveFile(payload: {
    filename: string;
    token: string;
  }): Promise<{ saved: boolean; uri: string }>;
  pickFile(): Promise<{ content: string; filename: string; uri: string }>;
}

const PythonBridge = registerPlugin<PythonBridgePlugin>("PythonBridge");

export function isAndroidNative(): boolean {
  return Capacitor.getPlatform() === "android";
}

export async function probePython(): Promise<PythonProbeResult> {
  return PythonBridge.probe();
}

export async function requestPython<T>(
  path: string,
  method = "GET",
  body?: string,
): Promise<T> {
  const response = await PythonBridge.request({
    path,
    method,
    body: body ?? "",
  });
  return JSON.parse(response.payload) as T;
}

export async function saveTextFile(filename: string, content: string): Promise<void> {
  const { token } = await PythonBridge.prepareSaveFile({ content });
  await PythonBridge.saveFile({ filename, token });
}

export async function pickTextFile(): Promise<string> {
  const result = await PythonBridge.pickFile();
  return result.content;
}
