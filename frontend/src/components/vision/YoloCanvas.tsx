import { useEffect, useRef } from 'react'
import { YoloDetection } from '../../api/vision'

const LABEL_COLORS: Record<string, string> = {
  person:   '#ef4444',
  weapon:   '#dc2626',
  aircraft: '#3b82f6',
  vehicle:  '#f59e0b',
  ship:     '#06b6d4',
  default:  '#10b981',
}

function colorFor(label: string): string {
  const lower = label.toLowerCase()
  for (const [key, color] of Object.entries(LABEL_COLORS)) {
    if (lower.includes(key)) return color
  }
  return LABEL_COLORS.default
}

interface YoloCanvasProps {
  imgSrc: string            // object URL or data URI
  detections: YoloDetection[]
  modelWidth: number        // model inference resolution (e.g. 640)
  modelHeight: number
}

export function YoloCanvas({ imgSrc, detections, modelWidth, modelHeight }: YoloCanvasProps) {
  const imgRef    = useRef<HTMLImageElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  function draw() {
    const img = imgRef.current
    const canvas = canvasRef.current
    if (!img || !canvas) return

    canvas.width  = img.offsetWidth
    canvas.height = img.offsetHeight

    const scaleX = img.offsetWidth  / modelWidth
    const scaleY = img.offsetHeight / modelHeight

    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    for (const det of detections) {
      const [x1, y1, x2, y2] = det.bbox
      const rx = x1 * scaleX
      const ry = y1 * scaleY
      const rw = (x2 - x1) * scaleX
      const rh = (y2 - y1) * scaleY
      const color = colorFor(det.label)

      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(rx, ry, rw, rh)

      // Label background
      const labelText = `${det.label} ${Math.round(det.confidence * 100)}%`
      ctx.font = '11px system-ui'
      const textW = ctx.measureText(labelText).width
      ctx.fillStyle = color
      ctx.fillRect(rx - 1, ry - 18, textW + 6, 18)
      ctx.fillStyle = '#ffffff'
      ctx.fillText(labelText, rx + 2, ry - 4)
    }
  }

  useEffect(() => {
    const img = imgRef.current
    if (!img) return
    if (img.complete) { draw(); return }
    img.addEventListener('load', draw)
    return () => img.removeEventListener('load', draw)
  })

  // Redraw on resize
  useEffect(() => {
    const observer = new ResizeObserver(draw)
    if (imgRef.current) observer.observe(imgRef.current)
    return () => observer.disconnect()
  })

  return (
    <div className="relative inline-block" role="img" aria-label="Image with YOLO object detections">
      <img
        ref={imgRef}
        src={imgSrc}
        alt="Analysed image"
        className="max-w-full rounded"
        loading="lazy"
        decoding="async"
      />
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
      />
    </div>
  )
}
