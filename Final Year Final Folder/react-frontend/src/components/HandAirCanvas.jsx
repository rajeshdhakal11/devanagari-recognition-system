import React, { useEffect, useRef, useState, useCallback } from 'react';
import { HandLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import { toast } from 'react-hot-toast';

// Connections used to draw a minimal skeleton on the overlay
const HAND_CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],
  [0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],
  [13,17],[17,18],[18,19],[19,20],[0,17]
];

/**
 * HandAirCanvas
 * Props:
 *   canvasRef  – React ref to the drawing <canvas> in Dashboard
 *   onDrawing   – callback fired whenever a stroke is added (to trigger sync)
 *   onPointer   – callback for live fingertip cursor on main canvas
 *   trailFadeMs – live cursor trail fade duration in ms
 *   onTrailFadeChange – callback to update trail fade duration
 */
const HandAirCanvas = ({ canvasRef, onDrawing, onPointer, trailFadeMs = 120, onTrailFadeChange }) => {
  const videoRef       = useRef(null);
  const overlayRef     = useRef(null);
  const landmarkerRef  = useRef(null);
  const animFrameRef   = useRef(null);
  const streamRef      = useRef(null);
  const lastPosRef     = useRef(null);
  const smoothPosRef   = useRef(null);
  const penDownRef     = useRef(false);
  const drawStreakRef  = useRef(0);
  const pointerMotionRef = useRef({ x: 0, y: 0, t: 0, speed: 0 });

  const [active,       setActive]       = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [loadingMsg,   setLoadingMsg]   = useState('');
  const [penDown,      setPenDown]      = useState(false);
  const [handSeen,     setHandSeen]     = useState(false);

  // ── gesture: index finger extended + middle/ring/pinky curled ──────────────
  const isIndexOnly = (lm) => {
    const yAbove = (tip, pip) => lm[tip].y < lm[pip].y;
    return (
      yAbove(8, 6) &&           // index up
      !yAbove(12, 10) &&        // middle down
      !yAbove(16, 14) &&        // ring down
      !yAbove(20, 18) &&        // pinky down
      lm[8].y < lm[5].y         // keep index clearly above knuckle
    );
  };

  const smoothPoint = useCallback((nx, ny) => {
    const alpha = 0.5;
    if (!smoothPosRef.current) {
      smoothPosRef.current = { x: nx, y: ny };
      return smoothPosRef.current;
    }

    smoothPosRef.current = {
      x: smoothPosRef.current.x * (1 - alpha) + nx * alpha,
      y: smoothPosRef.current.y * (1 - alpha) + ny * alpha,
    };
    return smoothPosRef.current;
  }, []);

  // ── draw a single segment / dot on the main canvas ────────────────────────
  const paintOnCanvas = useCallback((nx, ny) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const cx = nx * canvas.width;
    const cy = ny * canvas.height;

    if (!lastPosRef.current) {
      ctx.beginPath();
      ctx.arc(cx, cy, ctx.lineWidth / 2.4, 0, Math.PI * 2);
      ctx.fillStyle = '#111827';
      ctx.fill();
    } else {
      ctx.beginPath();
      ctx.moveTo(lastPosRef.current.x, lastPosRef.current.y);
      ctx.lineTo(cx, cy);
      ctx.stroke();
    }
    lastPosRef.current = { x: cx, y: cy };
    onDrawing?.();
  }, [canvasRef, onDrawing]);

  // ── draw webcam overlay: skeleton + fingertip indicator ───────────────────
  const paintOverlay = useCallback((lm) => {
    const ov = overlayRef.current;
    if (!ov) return;
    const ctx = ov.getContext('2d');
    ctx.clearRect(0, 0, ov.width, ov.height);

    // Skeleton lines (mirrored x)
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1.5;
    for (const [a, b] of HAND_CONNECTIONS) {
      ctx.beginPath();
      ctx.moveTo((1 - lm[a].x) * ov.width, lm[a].y * ov.height);
      ctx.lineTo((1 - lm[b].x) * ov.width, lm[b].y * ov.height);
      ctx.stroke();
    }

    // Fingertip dot
    const tx = (1 - lm[8].x) * ov.width;
    const ty = lm[8].y * ov.height;
    ctx.beginPath();
    ctx.arc(tx, ty, 11, 0, Math.PI * 2);
    ctx.fillStyle = penDownRef.current
      ? 'rgba(251,146,60,0.92)'
      : 'rgba(139,92,246,0.80)';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }, []);

  // ── RAF detection loop ────────────────────────────────────────────────────
  const detect = useCallback(() => {
    const lm     = landmarkerRef.current;
    const video  = videoRef.current;
    if (!lm || !video || video.readyState < 2) {
      animFrameRef.current = requestAnimationFrame(detect);
      return;
    }

    const result = lm.detectForVideo(video, performance.now());
    if (result.landmarks?.length > 0) {
      const hand = result.landmarks[0];
      setHandSeen(true);
      paintOverlay(hand);

      const smoothed = smoothPoint(1 - hand[8].x, hand[8].y); // mirror x
      const now = performance.now();

      if (pointerMotionRef.current.t > 0) {
        const dt = Math.max(1, now - pointerMotionRef.current.t);
        const dx = smoothed.x - pointerMotionRef.current.x;
        const dy = smoothed.y - pointerMotionRef.current.y;
        const normalizedSpeed = Math.sqrt(dx * dx + dy * dy) / (dt / 1000);
        pointerMotionRef.current.speed = normalizedSpeed;
      }

      pointerMotionRef.current.x = smoothed.x;
      pointerMotionRef.current.y = smoothed.y;
      pointerMotionRef.current.t = now;

      const drawingGesture = isIndexOnly(hand);
      drawStreakRef.current = drawingGesture
        ? Math.min(drawStreakRef.current + 1, 6)
        : Math.max(drawStreakRef.current - 1, 0);

      const shouldDraw = drawStreakRef.current >= 2;
      penDownRef.current = shouldDraw;
      setPenDown(shouldDraw);
      onPointer?.({
        visible: true,
        x: smoothed.x,
        y: smoothed.y,
        drawing: shouldDraw,
        speed: pointerMotionRef.current.speed,
      });

      if (shouldDraw) {
        paintOnCanvas(smoothed.x, smoothed.y);
      } else {
        lastPosRef.current = null;
      }
    } else {
      setHandSeen(false);
      setPenDown(false);
      penDownRef.current  = false;
      lastPosRef.current  = null;
      smoothPosRef.current = null;
      drawStreakRef.current = 0;
      pointerMotionRef.current = { x: 0, y: 0, t: 0, speed: 0 };
      onPointer?.({ visible: false });
      const ov = overlayRef.current;
      if (ov) ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
    }

    animFrameRef.current = requestAnimationFrame(detect);
  }, [onPointer, paintOnCanvas, paintOverlay, smoothPoint]);

  // ── start ─────────────────────────────────────────────────────────────────
  const startAirDraw = useCallback(async () => {
    setLoading(true);

    // Step 1: request camera first so permissions prompt shows early
    setLoadingMsg('Requesting camera…');
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: 320, height: 240 },
        audio: false,
      });
    } catch (camErr) {
      console.error('[AirDraw] Camera error:', camErr);
      setLoading(false);
      toast.error(`Camera blocked: ${camErr.message}. Allow camera access and try again.`);
      return;
    }

    // Step 2: load MediaPipe WASM — pinned to installed version, CPU fallback
    setLoadingMsg('Loading AI model…');
    try {
      // Use the exact version matching node_modules/@mediapipe/tasks-vision
      const WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm';
      const MODEL_URL =
        'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

      const vision = await FilesetResolver.forVisionTasks(WASM_URL);

      // Try GPU; silently fall back to CPU if not supported
      let handLandmarker;
      try {
        handLandmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
          runningMode: 'VIDEO',
          numHands: 1,
        });
      } catch {
        console.warn('[AirDraw] GPU delegate failed, retrying with CPU…');
        setLoadingMsg('Falling back to CPU…');
        handLandmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: 'CPU' },
          runningMode: 'VIDEO',
          numHands: 1,
        });
      }
      landmarkerRef.current = handLandmarker;

      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }

      setActive(true);
      setLoading(false);
      setLoadingMsg('');
      animFrameRef.current = requestAnimationFrame(detect);
      toast.success('Air drawing ready! Raise only your index finger to draw.');
    } catch (err) {
      console.error('[AirDraw] MediaPipe error:', err);
      // Release camera if model loading failed
      stream.getTracks().forEach((t) => t.stop());
      setLoading(false);
      setLoadingMsg('');
      toast.error(`Air drawing failed: ${err?.message ?? err}`);
    }
  }, [detect]);

  // ── stop ──────────────────────────────────────────────────────────────────
  const stopAirDraw = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;

    landmarkerRef.current?.close?.();
    landmarkerRef.current = null;

    lastPosRef.current = null;
    smoothPosRef.current = null;
    drawStreakRef.current = 0;
    pointerMotionRef.current = { x: 0, y: 0, t: 0, speed: 0 };
    penDownRef.current = false;
    setActive(false);
    setHandSeen(false);
    setPenDown(false);
    onPointer?.({ visible: false });

    const ov = overlayRef.current;
    if (ov) ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
  }, [onPointer]);

  useEffect(() => () => stopAirDraw(), [stopAirDraw]);

  // ── UI ────────────────────────────────────────────────────────────────────
  return (
    <div className="mt-3 rounded-2xl border border-violet-400/25 bg-gradient-to-br from-violet-600/10 via-purple-600/10 to-indigo-600/10 p-4">
      {/* header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.25em] text-violet-300 font-semibold">
            ✦ Air Drawing
          </p>
          <h3 className="text-base font-semibold text-white mt-1">
            Draw in Air Using Your Hand
          </h3>
          <p className="text-xs text-gray-300 mt-1">
            Point only your{' '}
            <span className="text-amber-300 font-semibold">index finger</span> toward the
            camera — it draws on the canvas. Curl or open your hand to lift the pen.
          </p>
        </div>

        <div className="flex gap-2 shrink-0">
          {!active ? (
            <button
              type="button"
              onClick={startAirDraw}
              disabled={loading}
              className="px-3 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors disabled:opacity-60 whitespace-nowrap"
            >
              {loading ? (
                <span className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  {loadingMsg || 'Loading…'}
                </span>
              ) : (
                '✦ Start Air Drawing'
              )}
            </button>
          ) : (
            <button
              type="button"
              onClick={stopAirDraw}
              className="px-3 py-2 rounded-xl border border-red-400/30 bg-red-500/10 text-red-200 text-xs font-semibold hover:bg-red-500/20 transition-colors"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      {/* webcam feed + status */}
      {active && (
        <div className="flex flex-wrap items-start gap-3">
          {/* camera preview */}
          <div className="relative rounded-xl overflow-hidden border border-violet-400/20 shrink-0">
            <video
              ref={videoRef}
              className="h-40 w-52 object-cover block"
              style={{ transform: 'scaleX(-1)' }}
              muted
              playsInline
            />
            <canvas
              ref={overlayRef}
              width={320}
              height={240}
              className="absolute inset-0 w-full h-full pointer-events-none"
              style={{ transform: 'scaleX(-1)' }}
            />
            {/* no-hand warning */}
            {!handSeen && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-xl">
                <p className="text-xs text-white/70 text-center px-2">
                  Show your hand to the camera
                </p>
              </div>
            )}
          </div>

          {/* status badge + tips */}
          <div className="flex flex-col gap-2 justify-center min-w-0">
            <div
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold border transition-colors ${
                penDown
                  ? 'bg-amber-400/20 text-amber-200 border-amber-300/30'
                  : 'bg-gray-800 text-gray-400 border-gray-700'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full transition-colors ${
                  penDown ? 'bg-amber-300 animate-pulse' : 'bg-gray-600'
                }`}
              />
              {penDown ? 'Pen Down — Drawing!' : 'Pen Up'}
            </div>

            <ul className="text-[11px] text-gray-400 space-y-1 max-w-[200px]">
              <li>☝️ Index finger only → <span className="text-amber-300">Draw</span></li>
              <li>✌️ Two+ fingers → <span className="text-gray-300">Pen Up</span></li>
              <li>✊ Fist → <span className="text-gray-300">Pen Up</span></li>
              <li>🖐️ Open palm → <span className="text-gray-300">Pen Up</span></li>
            </ul>

            <div className="mt-1 w-full max-w-[240px]">
              <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.12em] text-violet-200/90">
                <span>Trail Persistence</span>
                <span>{trailFadeMs}ms</span>
              </div>
              <input
                type="range"
                min={80}
                max={260}
                step={10}
                value={trailFadeMs}
                onChange={(event) => onTrailFadeChange?.(Number(event.target.value))}
                className="mt-1 w-full accent-violet-400"
              />
              <div className="flex items-center justify-between text-[10px] text-gray-400">
                <span>Short</span>
                <span>Long</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HandAirCanvas;
