'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Eraser, Palette, Trash2, Minimize2, Maximize2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Card } from '../ui/card';

interface CanvasPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  currentQ: number;
  onSaveSnapshot: (qIndex: number, dataUrl: string) => void;
  snapshot?: string;
}

export function CanvasPanel({
  isOpen,
  onToggle,
  currentQ,
  onSaveSnapshot,
  snapshot,
}: CanvasPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentTool, setCurrentTool] = useState('pen');
  const [currentColor, setCurrentColor] = useState('#1e293b');
  const [lineWidth, setLineWidth] = useState(3);
  const lastPos = useRef({ x: 0, y: 0 });

  // Canvas functions
  const getCanvasPos = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
    };
  };

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    setIsDrawing(true);
    lastPos.current = getCanvasPos(e);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing) return;
    e.preventDefault();
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    const pos = getCanvasPos(e);
    ctx.beginPath();
    ctx.moveTo(lastPos.current.x, lastPos.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.strokeStyle = currentTool === 'eraser' ? '#ffffff' : currentColor;
    ctx.lineWidth = currentTool === 'eraser' ? lineWidth * 4 : lineWidth;
    ctx.lineCap = 'round';
    ctx.stroke();
    lastPos.current = pos;
  };

  const stopDrawing = useCallback(() => {
    if (isDrawing) {
      setIsDrawing(false);
      // Save snapshot
      const canvas = canvasRef.current;
      if (canvas) {
        onSaveSnapshot(currentQ, canvas.toDataURL('image/png'));
      }
    }
  }, [isDrawing, currentQ, onSaveSnapshot]);

  const clearCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    onSaveSnapshot(currentQ, '');
  }, [currentQ, onSaveSnapshot]);

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = canvas?.parentElement;
    if (!canvas || !container) return;

    // Save current content before resize
    const ctx = canvas.getContext('2d');
    let imageData: ImageData | null = null;
    if (ctx && canvas.width > 0 && canvas.height > 0) {
      imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    }

    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    // Restore white background
    if (ctx) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }, []);

  // Restore snapshot when question changes
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    // Resize first
    resizeCanvas();

    if (snapshot) {
      const img = new Image();
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
      };
      img.src = snapshot;
    } else {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }, [snapshot, currentQ, resizeCanvas]);

  useEffect(() => {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, [resizeCanvas]);

  if (!isOpen) {
    return (
      <Button
        variant="outline"
        size="sm"
        className="fixed right-4 top-24 z-10 shadow-md"
        onClick={onToggle}
      >
        <Maximize2 className="h-4 w-4 mr-1" />
        Open Workspace
      </Button>
    );
  }

  return (
    <Card className="w-80 border-l flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b flex items-center justify-between">
        <span className="font-medium text-sm">Workspace</span>
        <Button variant="ghost" size="sm" onClick={onToggle}>
          <Minimize2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Toolbar */}
      <div className="p-3 border-b flex items-center gap-2 flex-wrap">
        <Button
          variant={currentTool === 'pen' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setCurrentTool('pen')}
        >
          <Palette className="h-4 w-4" />
        </Button>
        <Button
          variant={currentTool === 'eraser' ? 'default' : 'ghost'}
          size="sm"
          onClick={() => setCurrentTool('eraser')}
        >
          <Eraser className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="sm" onClick={clearCanvas}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>

        <div className="flex gap-1 ml-auto">
          {['#1e293b', '#ef4444', '#3b82f6', '#10b981'].map((color) => (
            <button
              key={color}
              className={`w-6 h-6 rounded-full border-2 ${
                currentColor === color && currentTool === 'pen'
                  ? 'border-primary'
                  : 'border-transparent'
              }`}
              style={{ backgroundColor: color }}
              onClick={() => {
                setCurrentColor(color);
                setCurrentTool('pen');
              }}
            />
          ))}
        </div>

        <input
          type="range"
          min="1"
          max="10"
          value={lineWidth}
          onChange={(e) => setLineWidth(parseInt(e.target.value))}
          className="w-16"
        />
      </div>

      {/* Canvas */}
      <div className="flex-1 relative bg-white">
        <canvas
          ref={canvasRef}
          className="absolute inset-0 cursor-crosshair touch-none"
          onMouseDown={startDrawing}
          onMouseMove={draw}
          onMouseUp={stopDrawing}
          onMouseLeave={stopDrawing}
          onTouchStart={startDrawing}
          onTouchMove={draw}
          onTouchEnd={stopDrawing}
        />
      </div>
    </Card>
  );
}
