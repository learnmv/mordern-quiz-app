'use client';

import { useEffect, useRef, useState } from 'react';
import { fabric } from 'fabric';
import type { DiagramSpec } from '@/types';

interface DiagramRendererProps {
  diagram: DiagramSpec;
  interactive?: boolean;
  onDraw?: (data: any) => void;
}

export function DiagramRenderer({ diagram, interactive, onDraw }: DiagramRendererProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fabricCanvasRef = useRef<fabric.Canvas | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!canvasRef.current) return;

    // Initialize Fabric.js canvas
    const canvas = new fabric.Canvas(canvasRef.current, {
      width: diagram.width,
      height: diagram.height,
      backgroundColor: '#ffffff',
      selection: interactive,
    });

    fabricCanvasRef.current = canvas;
    setIsReady(true);

    return () => {
      canvas.dispose();
      fabricCanvasRef.current = null;
    };
  }, [diagram.width, diagram.height, interactive]);

  useEffect(() => {
    if (!isReady || !fabricCanvasRef.current) return;

    const canvas = fabricCanvasRef.current;
    canvas.clear();

    // Render based on diagram type
    switch (diagram.type) {
      case 'coordinate':
        renderCoordinatePlane(canvas, diagram.data);
        break;
      case 'chart':
        renderChart(canvas, diagram.data);
        break;
      case 'svg':
        renderSVG(canvas, diagram.data);
        break;
    }

    canvas.renderAll();
  }, [isReady, diagram]);

  // Set up interactive mode
  useEffect(() => {
    if (!isReady || !fabricCanvasRef.current || !interactive) return;

    const canvas = fabricCanvasRef.current;

    // Enable drawing mode
    canvas.isDrawingMode = true;
    canvas.freeDrawingBrush.width = 2;
    canvas.freeDrawingBrush.color = '#000000';

    // Handle object additions for interactive elements
    canvas.on('object:added', (e) => {
      if (onDraw) {
        onDraw({
          type: 'object:added',
          target: e.target,
          canvas: canvas.toJSON(),
        });
      }
    });

    return () => {
      canvas.off('object:added');
    };
  }, [isReady, interactive, onDraw]);

  return (
    <div className="border rounded-lg overflow-hidden bg-white">
      <canvas ref={canvasRef} />
    </div>
  );
}

// Render coordinate plane with grid, axes, points, and shapes
function renderCoordinatePlane(canvas: fabric.Canvas, data: any) {
  const { grid, points = [], shapes = [], lines = [] } = data;
  const width = canvas.width || 400;
  const height = canvas.height || 400;

  const xMin = grid?.xMin ?? -10;
  const xMax = grid?.xMax ?? 10;
  const yMin = grid?.yMin ?? -10;
  const yMax = grid?.yMax ?? 10;
  const step = grid?.step ?? 1;

  const xRange = xMax - xMin;
  const yRange = yMax - yMin;
  const scaleX = width / xRange;
  const scaleY = height / yRange;

  // Helper to convert coordinate to canvas position
  const toCanvasX = (x: number) => (x - xMin) * scaleX;
  const toCanvasY = (y: number) => height - (y - yMin) * scaleY;

  // Draw grid lines
  const gridColor = '#e5e7eb';
  const axisColor = '#374151';

  // Vertical grid lines
  for (let x = xMin; x <= xMax; x += step) {
    const canvasX = toCanvasX(x);
    canvas.add(new fabric.Line([canvasX, 0, canvasX, height], {
      stroke: x === 0 ? axisColor : gridColor,
      strokeWidth: x === 0 ? 2 : 1,
      selectable: false,
    }));
  }

  // Horizontal grid lines
  for (let y = yMin; y <= yMax; y += step) {
    const canvasY = toCanvasY(y);
    canvas.add(new fabric.Line([0, canvasY, width, canvasY], {
      stroke: y === 0 ? axisColor : gridColor,
      strokeWidth: y === 0 ? 2 : 1,
      selectable: false,
    }));
  }

  // Draw shapes
  shapes.forEach((shape: any) => {
    if (shape.type === 'polygon' && shape.points) {
      const fabricPoints = shape.points.map((p: any) => ({
        x: toCanvasX(p.x),
        y: toCanvasY(p.y),
      }));

      canvas.add(new fabric.Polygon(fabricPoints, {
        fill: shape.fill || 'rgba(59, 130, 246, 0.2)',
        stroke: shape.stroke || '#3b82f6',
        strokeWidth: 2,
        selectable: false,
      }));
    }
  });

  // Draw lines
  lines.forEach((line: any) => {
    canvas.add(new fabric.Line([
      toCanvasX(line.from.x),
      toCanvasY(line.from.y),
      toCanvasX(line.to.x),
      toCanvasY(line.to.y),
    ], {
      stroke: line.color || '#000000',
      strokeWidth: line.width || 2,
      strokeDashArray: line.style === 'dashed' ? [5, 5] : undefined,
      selectable: false,
    }));
  });

  // Draw points
  points.forEach((point: any) => {
    const circle = new fabric.Circle({
      left: toCanvasX(point.x) - 5,
      top: toCanvasY(point.y) - 5,
      radius: 5,
      fill: point.color || '#ef4444',
      stroke: '#000000',
      strokeWidth: 1,
      selectable: false,
    });
    canvas.add(circle);

    // Add label if provided
    if (point.label) {
      const text = new fabric.Text(point.label, {
        left: toCanvasX(point.x) + 8,
        top: toCanvasY(point.y) - 8,
        fontSize: 14,
        fill: '#000000',
        selectable: false,
      });
      canvas.add(text);
    }
  });
}

// Render charts (histograms, box plots, dot plots)
function renderChart(canvas: fabric.Canvas, data: any) {
  const { chartType, config, options } = data;
  const width = canvas.width || 500;
  const height = canvas.height || 300;

  const padding = { top: 40, right: 40, bottom: 60, left: 60 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Draw axes
  canvas.add(new fabric.Line([padding.left, padding.top, padding.left, height - padding.bottom], {
    stroke: '#374151',
    strokeWidth: 2,
    selectable: false,
  }));

  canvas.add(new fabric.Line([padding.left, height - padding.bottom, width - padding.right, height - padding.bottom], {
    stroke: '#374151',
    strokeWidth: 2,
    selectable: false,
  }));

  if (chartType === 'histogram' && config?.labels && config?.datasets) {
    const labels = config.labels;
    const dataset = config.datasets[0];
    const values = dataset.data;
    const maxValue = Math.max(...values);

    const barWidth = chartWidth / labels.length * 0.8;
    const barSpacing = chartWidth / labels.length * 0.2;

    values.forEach((value: number, index: number) => {
      const barHeight = (value / maxValue) * chartHeight;
      const x = padding.left + index * (barWidth + barSpacing) + barSpacing / 2;
      const y = height - padding.bottom - barHeight;

      // Draw bar
      canvas.add(new fabric.Rect({
        left: x,
        top: y,
        width: barWidth,
        height: barHeight,
        fill: dataset.backgroundColor || '#3b82f6',
        stroke: '#1d4ed8',
        strokeWidth: 1,
        selectable: false,
      }));

      // Draw label
      canvas.add(new fabric.Text(labels[index], {
        left: x + barWidth / 2 - 15,
        top: height - padding.bottom + 10,
        fontSize: 12,
        fill: '#374151',
        selectable: false,
      }));

      // Draw value on top
      canvas.add(new fabric.Text(value.toString(), {
        left: x + barWidth / 2 - 5,
        top: y - 20,
        fontSize: 12,
        fill: '#374151',
        selectable: false,
      }));
    });
  }

  // Draw axis labels if provided
  if (options?.scales?.y?.title) {
    canvas.add(new fabric.Text(options.scales.y.title, {
      left: 10,
      top: height / 2,
      fontSize: 12,
      fill: '#374151',
      angle: -90,
      selectable: false,
    }));
  }
}

// Render SVG-based diagrams (geometric shapes)
function renderSVG(canvas: fabric.Canvas, data: any) {
  const { paths = [], labels = [], dimensions = [] } = data;
  const width = canvas.width || 300;
  const height = canvas.height || 200;

  // Draw paths
  paths.forEach((path: any) => {
    canvas.add(new fabric.Path(path.d, {
      fill: path.fill || 'transparent',
      stroke: path.stroke || '#000000',
      strokeWidth: 2,
      selectable: false,
    }));
  });

  // Draw labels
  labels.forEach((label: any) => {
    canvas.add(new fabric.Text(label.text, {
      left: label.x,
      top: label.y,
      fontSize: label.fontSize || 14,
      fill: label.color || '#000000',
      selectable: false,
    }));
  });

  // Draw dimension lines
  dimensions.forEach((dim: any) => {
    // Draw dimension line
    canvas.add(new fabric.Line([
      dim.from.x, dim.from.y,
      dim.to.x, dim.to.y,
    ], {
      stroke: '#374151',
      strokeWidth: 1,
      selectable: false,
    }));

    // Draw dimension text
    const midX = (dim.from.x + dim.to.x) / 2;
    const midY = (dim.from.y + dim.to.y) / 2;
    canvas.add(new fabric.Text(dim.label, {
      left: midX - 15,
      top: midY - 20,
      fontSize: 12,
      fill: '#374151',
      selectable: false,
    }));
  });
}
