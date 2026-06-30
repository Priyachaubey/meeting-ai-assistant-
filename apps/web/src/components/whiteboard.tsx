"use client";

import { useEffect, useRef, useState } from "react";
import { Pencil, Square, Circle as CircleIcon, Minus, Type, Eraser, Undo2, Redo2, Trash2, Download, FileDown } from "lucide-react";
import { cn } from "@/lib/utils";

type Tool = "pencil" | "rectangle" | "ellipse" | "line" | "text" | "eraser";

interface Stroke {
  id: string;
  user_id: string;
  tool: Tool;
  points: number[];
  color: string;
  width: number;
  text: string | null;
}

const COLORS = ["#101116", "#ff6b5f", "#2dd4bf", "#5B0A8C", "#f59e0b", "#3b82f6"] as const;

/** Draws one stroke onto a canvas 2D context. Shared between the live drawing loop and the
 * full-history redraw, so there's exactly one place that knows how to render each tool —
 * the alternative (slightly different logic for "draw live" vs "replay history") is a
 * classic source of subtle rendering mismatches between what you see while drawing and what
 * actually gets persisted/exported. */
function drawStroke(ctx: CanvasRenderingContext2D, stroke: Stroke) {
  ctx.strokeStyle = stroke.color;
  ctx.fillStyle = stroke.color;
  ctx.lineWidth = stroke.width;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  if (stroke.tool === "pencil" || stroke.tool === "eraser") {
    if (stroke.tool === "eraser") {
      ctx.globalCompositeOperation = "destination-out";
      ctx.lineWidth = stroke.width * 4; // eraser reads better chunkier than the pencil width it shares a slider with
    } else {
      ctx.globalCompositeOperation = "source-over";
    }
    ctx.beginPath();
    for (let i = 0; i < stroke.points.length; i += 2) {
      const x = stroke.points[i], y = stroke.points[i + 1];
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalCompositeOperation = "source-over";
  } else if (stroke.tool === "rectangle" && stroke.points.length >= 4) {
    const [x1, y1, x2, y2] = stroke.points;
    ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
  } else if (stroke.tool === "ellipse" && stroke.points.length >= 4) {
    const [x1, y1, x2, y2] = stroke.points;
    const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
    ctx.beginPath();
    ctx.ellipse(cx, cy, Math.abs(x2 - x1) / 2, Math.abs(y2 - y1) / 2, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else if (stroke.tool === "line" && stroke.points.length >= 4) {
    const [x1, y1, x2, y2] = stroke.points;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  } else if (stroke.tool === "text" && stroke.text && stroke.points.length >= 2) {
    ctx.font = `${Math.max(stroke.width * 6, 16)}px sans-serif`;
    ctx.fillText(stroke.text, stroke.points[0], stroke.points[1]);
  }
}

export function Whiteboard({
  initialStrokes, onDraw, onUndo, onRedo, onClear,
}: {
  initialStrokes: Stroke[];
  onDraw: (stroke: Omit<Stroke, "id" | "user_id">) => void;
  onUndo: () => void;
  onRedo: () => void;
  onClear: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [strokes, setStrokes] = useState<Stroke[]>(initialStrokes);
  const [tool, setTool] = useState<Tool>("pencil");
  const [color, setColor] = useState<string>(COLORS[0]);
  const [width, setWidth] = useState(3);
  const drawingRef = useRef(false);
  const currentPointsRef = useRef<number[]>([]);
  const startPointRef = useRef<[number, number] | null>(null);

  // Keep in sync with strokes arriving from elsewhere (other participants, or our own
  // optimistic draw being echoed back) — see the parent's WS handler for where these flow
  // in via setWhiteboardStrokes, which this component re-renders from via the
  // initialStrokes prop changing identity each time.
  useEffect(() => { setStrokes(initialStrokes); }, [initialStrokes]);

  // Full redraw whenever the stroke list changes — simplest-correct approach for a
  // shared-state canvas (no incremental patching to get subtly wrong); strokes counts in the
  // hundreds at most for a meeting-length whiteboard session, well within what redrawing on
  // every change costs on a modern canvas.
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (const stroke of strokes) drawStroke(ctx, stroke);
  }, [strokes]);

  // Resize the canvas's actual pixel buffer to match its displayed size, including
  // devicePixelRatio — skipping this makes drawing blurry on any HiDPI screen, and skipping
  // the resize entirely on container size changes would clip the board on smaller screens.
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = container.clientWidth * dpr;
      canvas.height = container.clientHeight * dpr;
      canvas.style.width = `${container.clientWidth}px`;
      canvas.style.height = `${container.clientHeight}px`;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.scale(dpr, dpr);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, container.clientWidth, container.clientHeight);
        for (const stroke of strokes) drawStroke(ctx, stroke);
      }
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function getPoint(e: React.PointerEvent<HTMLCanvasElement>): [number, number] {
    const rect = canvasRef.current!.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  function handlePointerDown(e: React.PointerEvent<HTMLCanvasElement>) {
    const [x, y] = getPoint(e);
    if (tool === "text") {
      const text = window.prompt("Text:");
      if (text) onDraw({ tool: "text", points: [x, y], color, width, text });
      return;
    }
    drawingRef.current = true;
    startPointRef.current = [x, y];
    currentPointsRef.current = tool === "pencil" || tool === "eraser" ? [x, y] : [x, y, x, y];
  }

  function handlePointerMove(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    const [x, y] = getPoint(e);
    const ctx = canvasRef.current!.getContext("2d");
    if (!ctx) return;

    if (tool === "pencil" || tool === "eraser") {
      currentPointsRef.current.push(x, y);
      // Live local preview as you draw, before the round-trip through the WS confirms it —
      // redrawn from authoritative state once the broadcast echoes back (see the strokes
      // effect above), so this optimistic segment never permanently diverges from reality.
      drawStroke(ctx, { id: "live", user_id: "", tool, points: currentPointsRef.current.slice(-4), color, width, text: null });
    } else {
      const [sx, sy] = startPointRef.current!;
      currentPointsRef.current = [sx, sy, x, y];
      ctx.clearRect(0, 0, canvasRef.current!.width, canvasRef.current!.height);
      for (const s of strokes) drawStroke(ctx, s);
      drawStroke(ctx, { id: "live", user_id: "", tool, points: currentPointsRef.current, color, width, text: null });
    }
  }

  function handlePointerUp() {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    if (currentPointsRef.current.length >= (tool === "pencil" || tool === "eraser" ? 2 : 4)) {
      onDraw({ tool, points: currentPointsRef.current, color, width, text: null });
    }
    currentPointsRef.current = [];
    startPointRef.current = null;
  }

  function handleExportPng() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement("a");
    link.download = "whiteboard.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
  }

  function handleExportPdf() {
    // No new dependency for this — a single full-page image inside a minimal, valid PDF
    // wrapper is simple enough to construct by hand (this is literally what "image-only PDF"
    // means at the format level) without pulling in a PDF library for one button. Browser
    // print-to-PDF would be the alternative but hijacks the whole page rather than exporting
    // just the board.
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    const base64 = dataUrl.split(",")[1];
    const binary = atob(base64);
    const imgBytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) imgBytes[i] = binary.charCodeAt(i);

    const w = canvas.width, h = canvas.height;
    const enc = new TextEncoder();
    const parts: Uint8Array[] = [];
    const offsets: number[] = [];
    let pos = 0;
    const push = (bytes: Uint8Array) => { parts.push(bytes); pos += bytes.length; };
    const pushStr = (s: string) => push(enc.encode(s));

    pushStr("%PDF-1.4\n");
    offsets[1] = pos; pushStr(`1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n`);
    offsets[2] = pos; pushStr(`2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n`);
    offsets[3] = pos; pushStr(`3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${w} ${h}] /Contents 4 0 R /Resources << /XObject << /Im0 5 0 R >> >> >>\nendobj\n`);
    const content = `q ${w} 0 0 ${h} 0 0 cm /Im0 Do Q`;
    offsets[4] = pos; pushStr(`4 0 obj\n<< /Length ${content.length} >>\nstream\n${content}\nendstream\nendobj\n`);
    offsets[5] = pos; pushStr(`5 0 obj\n<< /Type /XObject /Subtype /Image /Width ${w} /Height ${h} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${imgBytes.length} >>\nstream\n`);
    push(imgBytes);
    pushStr(`\nendstream\nendobj\n`);
    const xrefStart = pos;
    pushStr(`xref\n0 6\n0000000000 65535 f \n`);
    for (let i = 1; i <= 5; i++) pushStr(`${String(offsets[i]).padStart(10, "0")} 00000 n \n`);
    pushStr(`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`);

    const totalLen = parts.reduce((sum, p) => sum + p.length, 0);
    const pdfBytes = new Uint8Array(totalLen);
    let offset = 0;
    for (const p of parts) { pdfBytes.set(p, offset); offset += p.length; }

    const blob = new Blob([new Uint8Array(pdfBytes)], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.download = "whiteboard.pdf";
    link.href = url;
    link.click();
    URL.revokeObjectURL(url);
  }

  const tools: { id: Tool; icon: typeof Pencil; label: string }[] = [
    { id: "pencil", icon: Pencil, label: "Pencil" },
    { id: "rectangle", icon: Square, label: "Rectangle" },
    { id: "ellipse", icon: CircleIcon, label: "Ellipse" },
    { id: "line", icon: Minus, label: "Line" },
    { id: "text", icon: Type, label: "Text" },
    { id: "eraser", icon: Eraser, label: "Eraser" },
  ];

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-surface px-3 py-2">
        {tools.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setTool(id)}
            title={label}
            className={cn("grid h-8 w-8 place-items-center rounded-lg transition", tool === id ? "bg-brand text-white" : "text-ink-secondary hover:bg-surface-hover")}
          >
            <Icon className="h-4 w-4" />
          </button>
        ))}
        <div className="mx-1 h-6 w-px bg-surface-border" />
        {COLORS.map((c) => (
          <button
            key={c}
            onClick={() => setColor(c)}
            title={c}
            className={cn("h-6 w-6 rounded-full border-2 transition", color === c ? "border-ink scale-110" : "border-transparent")}
            style={{ backgroundColor: c }}
          />
        ))}
        <input
          type="range"
          min={1}
          max={12}
          value={width}
          onChange={(e) => setWidth(Number(e.target.value))}
          className="mx-1 w-16"
          title="Stroke width"
        />
        <div className="mx-1 h-6 w-px bg-surface-border" />
        <button onClick={onUndo} title="Undo" className="grid h-8 w-8 place-items-center rounded-lg text-ink-secondary transition hover:bg-surface-hover">
          <Undo2 className="h-4 w-4" />
        </button>
        <button onClick={onRedo} title="Redo" className="grid h-8 w-8 place-items-center rounded-lg text-ink-secondary transition hover:bg-surface-hover">
          <Redo2 className="h-4 w-4" />
        </button>
        <button onClick={onClear} title="Clear board" className="grid h-8 w-8 place-items-center rounded-lg text-[var(--danger)] transition hover:bg-[var(--danger)]/10">
          <Trash2 className="h-4 w-4" />
        </button>
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={handleExportPng} title="Export PNG" className="grid h-8 w-8 place-items-center rounded-lg text-ink-secondary transition hover:bg-surface-hover">
            <Download className="h-4 w-4" />
          </button>
          <button onClick={handleExportPdf} title="Export PDF" className="grid h-8 w-8 place-items-center rounded-lg text-ink-secondary transition hover:bg-surface-hover">
            <FileDown className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div ref={containerRef} className="relative flex-1 overflow-hidden">
        <canvas
          ref={canvasRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          className="absolute inset-0 h-full w-full touch-none cursor-crosshair"
        />
      </div>
    </div>
  );
}
