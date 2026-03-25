'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Loader2 } from 'lucide-react';

interface PullToRefreshProps {
  children: React.ReactNode;
  onRefresh: () => Promise<void>;
  threshold?: number;
}

export function PullToRefresh({
  children,
  onRefresh,
  threshold = 80,
}: PullToRefreshProps) {
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isPulling, setIsPulling] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const startYRef = useRef(0);
  const currentYRef = useRef(0);

  const canPull = useCallback(() => {
    // Only allow pull-to-refresh when scrolled to top
    return window.scrollY === 0;
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let isTouching = false;

    const handleTouchStart = (e: TouchEvent) => {
      if (!canPull() || isRefreshing) return;

      isTouching = true;
      startYRef.current = e.touches[0].clientY;
      currentYRef.current = startYRef.current;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isTouching || !canPull() || isRefreshing) return;

      currentYRef.current = e.touches[0].clientY;
      const distance = currentYRef.current - startYRef.current;

      if (distance > 0) {
        e.preventDefault();
        setIsPulling(true);
        // Apply resistance
        const adjustedDistance = Math.min(distance * 0.5, threshold * 1.5);
        setPullDistance(adjustedDistance);
      }
    };

    const handleTouchEnd = async () => {
      if (!isTouching) return;

      isTouching = false;

      if (pullDistance >= threshold) {
        setIsRefreshing(true);
        setPullDistance(threshold);

        try {
          await onRefresh();
        } catch (error) {
          console.error('Refresh failed:', error);
        }

        setIsRefreshing(false);
      }

      setIsPulling(false);
      setPullDistance(0);
    };

    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd, { passive: true });
    container.addEventListener('touchcancel', handleTouchEnd, { passive: true });

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);
      container.removeEventListener('touchcancel', handleTouchEnd);
    };
  }, [canPull, isRefreshing, onRefresh, pullDistance, threshold]);

  const progress = Math.min(pullDistance / threshold, 1);
  const shouldTrigger = pullDistance >= threshold;

  return (
    <div ref={containerRef} className="relative min-h-screen">
      {/* Pull indicator */}
      <div
        className="absolute left-0 right-0 flex items-center justify-center overflow-hidden pointer-events-none z-10"
        style={{
          top: 0,
          height: `${pullDistance}px`,
          opacity: isPulling || isRefreshing ? 1 : 0,
          transition: isPulling ? 'none' : 'all 0.3s ease-out',
        }}
      >
        <div
          className="flex items-center justify-center w-10 h-10 rounded-full bg-emerald-500/20"
          style={{
            transform: `scale(${0.5 + progress * 0.5}) rotate(${progress * 360}deg)`,
            transition: isPulling ? 'none' : 'transform 0.3s ease-out',
          }}
        >
          {isRefreshing ? (
            <Loader2 className="w-5 h-5 text-emerald-500 animate-spin" />
          ) : (
            <svg
              className={`w-5 h-5 transition-colors ${
                shouldTrigger ? 'text-emerald-500' : 'text-muted-foreground'
              }`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 5v14M5 12l7-7 7 7" />
            </svg>
          )}
        </div>
      </div>

      {/* Content */}
      <div
        style={{
          transform: `translateY(${pullDistance}px)`,
          transition: isPulling ? 'none' : 'transform 0.3s ease-out',
        }}
      >
        {children}
      </div>
    </div>
  );
}
