"use client";

import React, { useEffect, useRef } from "react";

export function BouncingBallsBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    // Mouse coordinates tracking
    const mouse = { x: -1000, y: -1000 };

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    const handleMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = -1000;
      mouse.y = -1000;
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("mousemove", handleMouseMove);
    document.body.addEventListener("mouseleave", handleMouseLeave);

    // Ball Class Definition
    class Ball {
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      color: string;

      constructor() {
        this.radius = Math.random() * 8 + 5; // size 5 to 13 px
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = (Math.random() - 0.5) * 0.4; // slow horizontal drift
        this.vy = -(Math.random() * 0.4 + 0.2); // float upwards
        this.color = "rgba(59, 130, 246, 0.3)"; 
      }

      draw(context: CanvasRenderingContext2D) {
        context.beginPath();
        // Radial gradient for a beautiful 3D glowing sphere bubble look
        const gradient = context.createRadialGradient(
          this.x - this.radius * 0.2,
          this.y - this.radius * 0.2,
          this.radius * 0.1,
          this.x,
          this.y,
          this.radius
        );
        gradient.addColorStop(0, "rgba(147, 197, 253, 0.7)");  // Soft bright highlight center
        gradient.addColorStop(0.35, "rgba(59, 130, 246, 0.35)"); // Translucent blue body
        gradient.addColorStop(1, "rgba(37, 99, 235, 0.0)");    // Fade edge out
        
        context.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        context.fillStyle = gradient;
        context.fill();
        context.closePath();
      }

      update() {
        // Floating wrap-around when hitting the top boundary
        if (this.y + this.radius < 0) {
          this.y = height + this.radius;
          this.x = Math.random() * width;
        }

        // Wall bounds bounce for X axis
        if (this.x + this.radius > width || this.x - this.radius < 0) {
          this.vx = -this.vx;
        }

        // Apply boundary clamp to prevent sticking
        this.x = Math.max(this.radius, Math.min(width - this.radius, this.x));

        // Interactive mouse repeller: pushes balls away if they get too close
        const dx = this.x - mouse.x;
        const dy = this.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const repelRadius = 130;

        if (dist < repelRadius) {
          const force = (repelRadius - dist) / repelRadius; // 0 to 1 scale
          const angle = Math.atan2(dy, dx);
          // Gently push velocity away from mouse
          this.vx += Math.cos(angle) * force * 0.15;
          this.vy += Math.sin(angle) * force * 0.15;
          
          // Clamp velocity to avoid infinite speed
          const maxSpeed = 3;
          const speed = Math.sqrt(this.vx * this.vx + this.vy * this.vy);
          if (speed > maxSpeed) {
            this.vx = (this.vx / speed) * maxSpeed;
            this.vy = (this.vy / speed) * maxSpeed;
          }
        }

        // Apply dampening to prevent continuous acceleration
        this.vx *= 0.99;
        this.vy *= 0.99;

        // Keep float baseline upward velocity active
        if (this.vy > -0.2) {
          this.vy -= 0.02;
        }

        // Move
        this.x += this.vx;
        this.y += this.vy;
      }
    }

    // Initialize 60 balls
    const ballsCount = 60;
    const balls: Ball[] = [];
    for (let i = 0; i < ballsCount; i++) {
      balls.push(new Ball());
    }

    // Animation Loop
    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      balls.forEach((ball) => {
        ball.update();
        ball.draw(ctx);
      });

      // Draw subtle connecting lines between nearby balls for interactive web look
      for (let i = 0; i < balls.length; i++) {
        for (let j = i + 1; j < balls.length; j++) {
          const dx = balls[i].x - balls[j].x;
          const dy = balls[i].y - balls[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(balls[i].x, balls[i].y);
            ctx.lineTo(balls[j].x, balls[j].y);
            // Draw line with blue opacity based on distance
            ctx.strokeStyle = `rgba(59, 130, 246, ${0.12 * (1 - dist / 120)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
            ctx.closePath();
          }
        }
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      document.body.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-0"
    />
  );
}
