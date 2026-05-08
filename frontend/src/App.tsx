import { useCallback, useEffect, useRef, useState } from "react";

type Session = { id: string; created_at: string; status: string };

type RoiItem = {
  id: number;
  session_id: string;
  frame_number: number;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  confidence: number | null;
  frame_width: number;
  frame_height: number;
  created_at: string;
};

type RoiResponse = { items: RoiItem[]; latest: RoiItem | null };

const apiBase = () => String(import.meta.env.VITE_API_BASE || "");

function wsUrl(path: string) {
  const base = apiBase() || `${window.location.protocol}//${window.location.host}`;
  const u = new URL("/api/v1" + path, base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  return u.toString();
}

function httpUrl(path: string) {
  const base = apiBase();
  return `${base}/api/v1${path}`;
}

export function App() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const ingestRef = useRef<WebSocket | null>(null);
  const previewRef = useRef<WebSocket | null>(null);
  const previewUrlRef = useRef<string | null>(null);
  const sendIntervalRef = useRef<number | null>(null);
  const roiIntervalRef = useRef<number | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectPendingRef = useRef(false);
  const reconnectEnabledRef = useRef(false);

  const [session, setSession] = useState<Session | null>(null);
  const [running, setRunning] = useState(false);
  const [lastAck, setLastAck] = useState<string>("");
  const [roi, setRoi] = useState<RoiResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [statusText, setStatusText] = useState<string>("Idle");

  const refreshRoi = useCallback(async (sessionId: string) => {
    const res = await fetch(httpUrl(`/sessions/${sessionId}/roi?limit=20`));
    if (!res.ok) {
      throw new Error(`ROI fetch failed (${res.status})`);
    }
    setRoi((await res.json()) as RoiResponse);
  }, []);

  const createSession = async () => {
    setError("");
    const res = await fetch(httpUrl("/sessions"), { method: "POST" });
    if (!res.ok) {
      setError(`Failed to create session (${res.status})`);
      return;
    }
    setSession((await res.json()) as Session);
  };

  const stopStreams = useCallback(() => {
    reconnectEnabledRef.current = false;
    reconnectPendingRef.current = false;
    reconnectAttemptsRef.current = 0;
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (sendIntervalRef.current) {
      window.clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }
    if (roiIntervalRef.current) {
      window.clearInterval(roiIntervalRef.current);
      roiIntervalRef.current = null;
    }
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;

    ingestRef.current?.close();
    previewRef.current?.close();
    ingestRef.current = null;
    previewRef.current = null;

    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setPreviewUrl("");

    setRunning(false);
    setStatusText("Stopped");
  }, []);

  const startCamera = useCallback(async () => {
    if (!session) return;
    setError("");
    setStatusText("Initializing camera...");
    stopStreams();
    reconnectEnabledRef.current = true;

    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    mediaStreamRef.current = stream;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      setError("Missing video/canvas elements");
      return;
    }
    setStatusText("Connecting streams...");
    video.srcObject = stream;
    await video.play();

    const ingest = new WebSocket(wsUrl(`/ws/sessions/${session.id}/ingest`));
    const preview = new WebSocket(wsUrl(`/ws/sessions/${session.id}/preview`));

    ingestRef.current = ingest;
    previewRef.current = preview;

    const scheduleReconnect = (reason: string) => {
      if (!reconnectEnabledRef.current || !session || reconnectPendingRef.current) return;
      reconnectPendingRef.current = true;
      const attempt = reconnectAttemptsRef.current + 1;
      reconnectAttemptsRef.current = attempt;
      const delayMs = Math.min(1000 * 2 ** (attempt - 1), 5000);
      setStatusText(`Reconnecting in ${Math.round(delayMs / 1000)}s...`);
      setError(reason);
      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectPendingRef.current = false;
        void startCamera().catch((e: unknown) => setError(String(e)));
      }, delayMs);
    };

    preview.binaryType = "blob";
    preview.addEventListener("message", (ev) => {
      const blob = ev.data as Blob;
      if (!(blob instanceof Blob)) return;
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(blob);
      previewUrlRef.current = url;
      setPreviewUrl(url);
    });

    ingest.addEventListener("message", (ev) => {
      setLastAck(String(ev.data));
    });

    ingest.addEventListener("error", () => setError("Ingest WebSocket error"));
    preview.addEventListener("error", () => setError("Preview WebSocket error"));
    ingest.addEventListener("close", (ev) => {
      if (ev.code !== 1000) scheduleReconnect(`Ingest stream closed (${ev.code})`);
    });
    preview.addEventListener("close", (ev) => {
      if (ev.code !== 1000) scheduleReconnect(`Preview stream closed (${ev.code})`);
    });

    await new Promise<void>((resolve, reject) => {
      let opened = 0;
      const bump = () => {
        opened += 1;
        if (opened === 2) resolve();
      };
      const fail = (label: string) => () => reject(new Error(`${label} WebSocket failed to open`));
      ingest.addEventListener("open", bump, { once: true });
      preview.addEventListener("open", bump, { once: true });
      ingest.addEventListener("error", fail("ingest"), { once: true });
      preview.addEventListener("error", fail("preview"), { once: true });
    });

    setRunning(true);
    reconnectAttemptsRef.current = 0;
    setStatusText("Streaming");

    const sendFrame = () => {
      const v = videoRef.current;
      const c = canvasRef.current;
      const ws = ingestRef.current;
      if (!v || !c || !ws || ws.readyState !== WebSocket.OPEN) return;
      const w = v.videoWidth;
      const h = v.videoHeight;
      if (!w || !h) return;
      c.width = w;
      c.height = h;
      const ctx = c.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(v, 0, 0, w, h);
      c.toBlob(
        (blob) => {
          if (!blob || ws.readyState !== WebSocket.OPEN) return;
          void blob.arrayBuffer().then((buf) => ws.send(buf));
        },
        "image/jpeg",
        0.75,
      );
    };

    sendIntervalRef.current = window.setInterval(sendFrame, 200);
    roiIntervalRef.current = window.setInterval(() => {
      void refreshRoi(session.id).catch((e: unknown) => setError(String(e)));
    }, 750);
  }, [refreshRoi, session, stopStreams]);

  useEffect(() => () => stopStreams(), [stopStreams]);

  return (
    <div className="layout">
      <h1>Mega AI — Face detection stream</h1>
      <div className="row">
        <button className="primary" type="button" onClick={() => void createSession()}>
          Create session
        </button>
        <button type="button" disabled={!session || running} onClick={() => void startCamera().catch((e) => setError(String(e)))}>
          Start camera + streams
        </button>
        <button type="button" disabled={!running} onClick={() => stopStreams()}>
          Stop
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      <div className="placeholder">Status: {statusText}</div>
      {session ? (
        <div className="panel" style={{ marginTop: 12 }}>
          <h2>Session</h2>
          <pre>{JSON.stringify(session, null, 2)}</pre>
        </div>
      ) : null}

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2>Camera</h2>
          <video ref={videoRef} playsInline muted />
          <canvas ref={canvasRef} style={{ display: "none" }} />
          {!running ? <p className="placeholder">Create a session, then start camera streaming.</p> : null}
        </div>
        <div className="panel">
          <h2>Processed feed (WebSocket preview)</h2>
          {previewUrl ? (
            <img alt="processed preview" src={previewUrl} />
          ) : (
            <div className="placeholder preview-placeholder">Processed stream will appear here.</div>
          )}
        </div>
      </div>

      <div className="grid" style={{ marginTop: 16 }}>
        <div className="panel">
          <h2>Last ingest ack</h2>
          <pre>{lastAck || "—"}</pre>
        </div>
        <div className="panel">
          <h2>ROI (REST)</h2>
          <pre>{roi ? JSON.stringify(roi.latest ?? roi.items[0] ?? null, null, 2) : "—"}</pre>
        </div>
      </div>
    </div>
  );
}
